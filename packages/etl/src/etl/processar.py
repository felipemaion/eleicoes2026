"""Processamento ZIP do TSE → Parquet validado (um arquivo por membro do ZIP).

Fluxo por membro: ler (tse_csv) → ligar município IBGE → regra específica da fonte →
gravar em arquivo temporário → conferir contrato e totais de controle → só então publicar
(rename). Um Parquet que viola o contrato ou não bate com a origem nunca é escrito.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import polars as pl
from contratos import CONTRATOS, Contrato, validar

from etl.fontes.catalogo import alvos
from etl.manifesto import Manifesto
from etl.tse_csv import ler_csv, membros_dados, scan_texto, transcodificar

LOG = logging.getLogger(__name__)
ELEITORADO = CONTRATOS["eleitorado_local_votacao"]
EXTERIOR = "ZZ"  # zonas do exterior não têm município IBGE
CROSSWALK = "municipio_tse_ibge"


class ErroProcessamento(RuntimeError):  # noqa: N818 - nome de domínio
    """Falha de regra de negócio no processamento (crosswalk, sal, totais de controle)."""


def cpf_valido(digitos: str) -> bool:
    """CPF com 11 dígitos, DVs corretos e não repetido (``00000000000``, ``11111111111``…)."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    nums = [int(d) for d in digitos]
    for n in (9, 10):
        resto = sum(d * (n + 1 - k) for k, d in enumerate(nums[:n])) * 10 % 11 % 10
        if resto != nums[n]:
            return False
    return True


def impressao_do_sal(sal: str) -> str:
    """``sha256(sal)[:12]``: identifica o sal no manifesto sem revelá-lo."""
    return hashlib.sha256(sal.encode()).hexdigest()[:12]


def _conferir_sal_do_manifesto(manifesto: Manifesto, grupo: str, proprio: str, sal: str) -> None:
    """Falha alto se outro ano do mesmo dataset foi processado com sal diferente.

    ``pessoa_id`` só liga 2022↔2026 se o sal for o mesmo; com sais distintos a interseção
    é vazia sem erro nenhum (incidente T-D06).
    """
    minha = impressao_do_sal(sal)
    for e in manifesto.entradas.values():
        if Path(e.caminho).parent.name != grupo or e.caminho == proprio:
            continue
        if e.sal_impressao and e.sal_impressao != minha:
            raise ErroProcessamento(
                f"sal do pessoa_id difere de {e.caminho} (impressão {e.sal_impressao} ≠ {minha}); "
                "use o mesmo PESSOA_ID_SAL e reprocesse todos os anos"
            )


def hash_pessoa(cpf: str | None, titulo: str | None, sal: str) -> str | None:
    """``sha256(sal || cpf_normalizado)`` (ADR 0004); sem CPF válido cai no título.

    CPF exige 11 dígitos com DV válido; título, 12 dígitos não repetidos. "Não divulgável"
    (``-4``), vazio ou malformado não identifica ninguém → ``None`` (nunca um hash de lixo,
    que ligaria pessoas diferentes ao mesmo ``pessoa_id``).
    """
    for bruto, valido in ((cpf, cpf_valido), (titulo, _titulo_valido)):
        if not bruto or bruto.strip().startswith("-"):
            continue
        digitos = re.sub(r"\D", "", bruto)
        if valido(digitos):
            return hashlib.sha256(sal.encode() + digitos.encode()).hexdigest()
    return None


def _titulo_valido(digitos: str) -> bool:
    return len(digitos) == 12 and len(set(digitos)) > 1


@dataclass(frozen=True)
class Contexto:
    """O que as regras específicas de cada fonte podem precisar."""

    ano: int
    sal: str | None
    raiz_raw: Path | None = None
    raiz_proc: Path | None = None


Regra = Callable[[pl.LazyFrame, Contexto], pl.LazyFrame]


def _pessoa_id(lf: pl.LazyFrame, ctx: Contexto) -> pl.LazyFrame:
    if not ctx.sal:
        raise ErroProcessamento("consulta_cand exige o sal do pessoa_id (variável PESSOA_ID_SAL)")
    sal = ctx.sal
    df = lf.collect()  # ~30 mil candidatos: cabe em memória
    ids = [
        hash_pessoa(c, t, sal)
        for c, t in zip(df["nr_cpf_candidato"], df["nr_titulo_eleitoral_candidato"], strict=True)
    ]
    # CPF/título saem aqui: só o hash segue adiante.
    return (
        df.drop("nr_cpf_candidato", "nr_titulo_eleitoral_candidato")
        .with_columns(pessoa_id=pl.Series(ids, dtype=pl.Utf8))
        .lazy()
    )


def _primeiro(coluna: str) -> pl.Expr:
    return pl.col(coluna).drop_nulls().first()


def _agregar_locais(lf: pl.LazyFrame, _: Contexto) -> pl.LazyFrame:
    # O TSE marca "sem coordenada" como (-1.0; -1.0). Locais do exterior (ZZ) ficam sem
    # coordenada: estão fora do Brasil, não entram em mapa nem em H3 (spec, §0 Recortes).
    sem_coord = (
        ((pl.col("nr_latitude") == -1.0) & (pl.col("nr_longitude") == -1.0))
        | (pl.col("sg_uf") == EXTERIOR)
        # lat/lon só valem em par: metade de coordenada nunca é mantida
        | (pl.col("nr_latitude").is_null() != pl.col("nr_longitude").is_null())
    )
    lat_lo, lat_hi = ELEITORADO.faixas["nr_latitude"]
    lon_lo, lon_hi = ELEITORADO.faixas["nr_longitude"]
    fora_do_brasil = (
        pl.col("nr_latitude").is_not_null()
        & ~sem_coord
        & ~(
            pl.col("nr_latitude").is_between(lat_lo, lat_hi)
            & pl.col("nr_longitude").is_between(lon_lo, lon_hi)
        )
    )
    # Erro conhecido da fonte (ex.: um local de MG com coordenada na Europa): anula e avisa.
    suspeitos = (
        lf.filter(fora_do_brasil)
        .select("sg_uf", "cd_municipio_tse", "nr_zona", "nr_local_votacao")
        .unique()
        .collect()
    )
    if suspeitos.height:
        LOG.warning(
            "%d local(is) com coordenada fora do Brasil anulada(s): %s",
            suspeitos.height,
            suspeitos.head(10).rows(),
        )
    invalida = sem_coord | fora_do_brasil
    lf = lf.with_columns(
        pl.when(invalida).then(None).otherwise(pl.col(c)).alias(c)
        for c in ("nr_latitude", "nr_longitude")
    )
    chave = [
        "aa_eleicao",
        "nr_turno",
        "sg_uf",
        "cd_municipio_tse",
        "cd_mun_ibge",
        "nr_zona",
        "nr_local_votacao",
    ]
    # Ordem total por seção: "primeira" coordenada/endereço do local não depende da ordem do CSV.
    # lat/lon saem de UMA mesma seção (struct), nunca de seções diferentes.
    lf = lf.sort(["nr_turno", pl.col("nr_secao").cast(pl.Int64, strict=False)], nulls_last=True)
    par = pl.struct("nr_latitude", "nr_longitude").filter(pl.col("nr_latitude").is_not_null())
    return lf.group_by(chave, maintain_order=True).agg(
        _primeiro("nm_local_votacao"), _primeiro("ds_endereco"), _primeiro("nm_bairro"),
        par.first().struct.field("nr_latitude"), par.first().struct.field("nr_longitude"),
        pl.len().cast(pl.Int32).alias("qt_secoes"),
        pl.col("qt_eleitor_secao").sum(),
        pl.col("dt_geracao").max(),
    )  # fmt: skip


def _normalizar_rotulos(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Rótulos ``ds_*``: só espaços (borda e repetidos) — caixa e acento seguem brutos."""
    cols = [c for c in lf.collect_schema().names() if c.startswith("ds_")]
    return lf.with_columns(pl.col(c).str.strip_chars().str.replace_all(r"\s+", " ") for c in cols)


def _agregar(lf: pl.LazyFrame, ct: Contrato, valor: str) -> pl.LazyFrame:
    """Lançamentos → um registro por candidatura × prestação × rótulos (``ct.colunas``)."""
    chaves = [c for c in ct.colunas if c not in (valor, "qt_lancamentos", "dt_geracao")]
    return _normalizar_rotulos(lf).group_by(chaves).agg(
        pl.col(valor).sum(),
        pl.len().cast(pl.Int32).alias("qt_lancamentos"),
        pl.col("dt_geracao").max(),
    )  # fmt: skip


def _mapa_prestador(ctx: Contexto) -> pl.DataFrame:
    """``sq_prestador_contas → sq_candidato`` das receitas e despesas contratadas do ano."""
    if ctx.raiz_raw is None or ctx.raiz_proc is None:
        raise ErroProcessamento("despesas pagas exigem raiz_raw/raiz_proc no contexto")
    partes = []
    for nome in ("receitas_candidatos", "despesas_contratadas_candidatos"):
        pasta = ctx.raiz_proc / nome / f"ano={ctx.ano}"
        if not list(pasta.glob("*.parquet")):
            processar_fonte(nome, ctx.ano, ctx.raiz_raw, ctx.raiz_proc)
        partes.append(
            pl.scan_parquet(pasta / "*.parquet").select("sq_prestador_contas", "sq_candidato")
        )
    mapa = pl.concat(partes).unique().collect()
    ambiguos = mapa.group_by("sq_prestador_contas").len().filter(pl.col("len") > 1)
    if ambiguos.height:
        raise ErroProcessamento(
            f"{ambiguos.height} prestador(es) ligado(s) a mais de um candidato: "
            f"{ambiguos['sq_prestador_contas'].head(5).to_list()}"
        )
    return mapa


def _despesas_pagas(lf: pl.LazyFrame, ctx: Contexto) -> pl.LazyFrame:
    """Liga cada pagamento à candidatura por ``SQ_PRESTADOR_CONTAS``; sem elo → erro."""
    mapa = _mapa_prestador(ctx).lazy()
    ligado = lf.join(mapa, on="sq_prestador_contas", how="left")
    sem = ligado.filter(pl.col("sq_candidato").is_null()).select("sq_prestador_contas").unique()
    orfaos = sem.collect()
    if orfaos.height:
        raise ErroProcessamento(
            f"{orfaos.height} prestador(es) de despesa paga sem candidatura: "
            f"{orfaos['sq_prestador_contas'].head(5).to_list()}"
        )
    return _agregar(ligado, CONTRATOS["despesas_pagas_candidatos"], "vr_pagto_despesa")


def _agregador(nome: str, valor: str) -> Regra:
    ct = CONTRATOS[nome]
    return lambda lf, _ctx: _agregar(lf, ct, valor)


@dataclass(frozen=True)
class Fonte:
    """Como processar uma fonte: contrato, soma de controle e regra opcional."""

    contrato: Contrato
    controle: tuple[str, ...] = ()  # colunas inteiras cuja soma deve bater com a origem
    linhas_1a1: bool = True  # saída tem tantas linhas quanto a entrada?
    extras: tuple[str, ...] = ()
    regra: Regra | None = None
    controle_decimal: tuple[str, ...] = ()  # somas em centavos (R$), exatas
    contagem: str | None = None  # coluna cuja soma deve igualar o nº de linhas do CSV
    zip_id: str | None = None  # id no catálogo, quando o ZIP traz vários datasets
    prefixo: str | None = None  # prefixo dos membros do dataset dentro do ZIP


FONTES: dict[str, Fonte] = {
    "municipio_tse_ibge": Fonte(CONTRATOS["municipio_tse_ibge"]),
    "consulta_cand": Fonte(
        CONTRATOS["consulta_cand"],
        extras=("nr_cpf_candidato", "nr_titulo_eleitoral_candidato"),
        regra=_pessoa_id,
    ),
    "consulta_vagas": Fonte(CONTRATOS["consulta_vagas"], controle=("qt_vaga",)),
    "votacao_candidato_munzona": Fonte(
        CONTRATOS["votacao_candidato_munzona"], controle=("qt_votos_nominais",)
    ),
    "detalhe_votacao_munzona": Fonte(
        CONTRATOS["detalhe_votacao_munzona"], controle=("qt_aptos", "qt_comparecimento")
    ),
    "votacao_partido_munzona": Fonte(
        CONTRATOS["votacao_partido_munzona"], controle=("qt_total_votos_leg_validos",)
    ),
    "eleitorado_local_votacao": Fonte(
        CONTRATOS["eleitorado_local_votacao"],
        controle=("qt_eleitor_secao",),
        linhas_1a1=False,
        extras=("nr_secao",),
        regra=_agregar_locais,
    ),
    **{
        nome: Fonte(
            CONTRATOS[nome],
            controle_decimal=(valor,),
            contagem="qt_lancamentos",
            zip_id="prestacao_contas",
            prefixo=nome,
            regra=regra,
        )
        for nome, valor, regra in (
            ("receitas_candidatos", "vr_receita", _agregador("receitas_candidatos", "vr_receita")),
            (
                "despesas_contratadas_candidatos",
                "vr_despesa_contratada",
                _agregador("despesas_contratadas_candidatos", "vr_despesa_contratada"),
            ),
            ("despesas_pagas_candidatos", "vr_pagto_despesa", _despesas_pagas),
        )
    },
}

CONTAS: tuple[str, ...] = (
    "receitas_candidatos",
    "despesas_contratadas_candidatos",
    "despesas_pagas_candidatos",
)


def _crosswalk(raiz_raw: Path, raiz_proc: Path, ano: int) -> pl.LazyFrame:
    """Tabela TSE→IBGE do ano; gera se ainda não existir."""
    pasta = raiz_proc / CROSSWALK / f"ano={ano}"
    if not list(pasta.glob("*.parquet")):
        processar_fonte(CROSSWALK, ano, raiz_raw, raiz_proc)
    return pl.scan_parquet(pasta / "*.parquet").select("cd_municipio_tse", "cd_mun_ibge")


def _conferir_municipios(saida: pl.LazyFrame, membro: str) -> None:
    sem = (
        saida.filter(pl.col("cd_mun_ibge").is_null() & (pl.col("sg_uf") != EXTERIOR))
        .select("cd_municipio_tse")
        .unique()
        .collect()
    )
    if sem.height:
        codigos = sorted(sem["cd_municipio_tse"].to_list())[:10]
        raise ErroProcessamento(
            f"{membro}: município(s) TSE sem correspondente IBGE no crosswalk: {codigos}"
        )


def _esperado_do_texto(csv: Path, fonte: Fonte, membro: str) -> dict[str, int]:
    """Totais de controle calculados do CSV **em texto**, independentes do parser.

    Inteiros: soma só valores ≥ 0 (``-1/-3/-4`` são sentinelas, não quantidades) e registra
    quantos foram sentinela ou não numéricos por coluna. Decimais (R$): soma em centavos,
    com sinal (estorno é negativo de verdade).
    """
    origem = fonte.contrato.origem
    exprs: list[pl.Expr] = [pl.len().alias("__n")]
    for c in fonte.controle:
        v = pl.col(origem.get(c, c.upper())).str.strip_chars()
        n = v.cast(pl.Int64, strict=False)
        exprs += [
            n.filter(n >= 0).sum().alias(c),
            (n < 0).sum().alias(f"__sentinela_{c}"),
            (n.is_null()).sum().alias(f"__nulo_{c}"),
        ]
    for c in fonte.controle_decimal:
        v = pl.col(origem.get(c, c.upper())).str.strip_chars().str.replace(",", ".")
        centavos = (v.cast(pl.Float64, strict=False) * 100).round().cast(pl.Int64)
        exprs += [centavos.sum().alias(c), centavos.is_null().sum().alias(f"__nulo_{c}")]
    r = scan_texto(csv).select(exprs).collect().row(0, named=True)
    for c in (*fonte.controle, *fonte.controle_decimal):
        LOG.info(
            "%s: %s → %d sentinela(s) negativa(s), %d nulo(s)/não numérico(s)",
            membro, c, r.get(f"__sentinela_{c}", 0), r[f"__nulo_{c}"],
        )  # fmt: skip
    colunas = (*fonte.controle, *fonte.controle_decimal)
    return {"__n": r["__n"], **{c: r[c] or 0 for c in colunas}}


def _controle(csv: Path, saida: pl.LazyFrame, fonte: Fonte, membro: str) -> None:
    """Total de controle: soma(CSV em texto) == soma(saída) e nº de linhas (1:1 ou contagem)."""
    esperado = _esperado_do_texto(csv, fonte, membro)
    linhas = pl.col(fonte.contagem).sum() if fonte.contagem else pl.len()
    obtido = (
        saida.select(
            linhas.alias("__n"),
            *[pl.col(c).sum().alias(c) for c in fonte.controle],
            *[
                (pl.col(c) * 100).round().cast(pl.Int64).sum().alias(c)
                for c in fonte.controle_decimal
            ],
        )
        .collect()
        .row(0, named=True)
    )
    obtido = {k: (v or 0) for k, v in obtido.items()}
    if not fonte.linhas_1a1 and not fonte.contagem:
        esperado.pop("__n")
        obtido.pop("__n")
    if esperado != obtido:
        raise ErroProcessamento(
            f"{membro}: totais de controle divergem: origem {esperado} × saída {obtido}"
        )


def _processar_membro(
    fonte: Fonte, zip_path: Path, membro: str, destino: Path, tmp: Path,
    ctx: Contexto, crosswalk: pl.LazyFrame | None,
) -> str | None:  # fmt: skip
    """Devolve o ``dt_geracao`` (máximo) do membro.

    O CSV transcodificado (com CPF/título) vive em ``tmp`` — fora de ``processed/`` — e é
    apagado ao fim do membro, qualquer que seja o resultado.
    """
    csv = tmp / (Path(membro).stem + ".utf8.csv")
    try:
        transcodificar(zip_path, membro, csv)
        lf = ler_csv(csv, membro, fonte.contrato, fonte.extras)
        if "cd_mun_ibge" in fonte.contrato.derivadas:
            if crosswalk is None:
                raise ErroProcessamento("crosswalk TSE→IBGE não carregado")
            lf = lf.join(crosswalk, on="cd_municipio_tse", how="left")
        if fonte.regra:
            lf = fonte.regra(lf, ctx)
        lf = lf.select(list(fonte.contrato.colunas))
        temporario = destino.with_name(destino.name + ".tmp")
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            lf.sink_parquet(temporario)
            saida = pl.scan_parquet(temporario)
            validar(saida, fonte.contrato)
            if "cd_mun_ibge" in fonte.contrato.derivadas:
                _conferir_municipios(saida, membro)
            _controle(csv, saida, fonte, membro)
            os.replace(temporario, destino)
        except BaseException:
            temporario.unlink(missing_ok=True)
            raise
    finally:
        csv.unlink(missing_ok=True)
    ultima = pl.scan_parquet(destino).select(pl.col("dt_geracao").max()).collect().item()
    return None if ultima is None else ultima.isoformat()


def _publicar(stage: Path, pasta: Path) -> None:
    """Troca ``ano=N.tmp/`` por ``ano=N/``: o leitor vê o ano antigo inteiro ou o novo inteiro."""
    antigo = pasta.with_name(pasta.name + ".old")
    shutil.rmtree(antigo, ignore_errors=True)
    if pasta.exists():
        os.replace(pasta, antigo)
    os.replace(stage, pasta)
    shutil.rmtree(antigo, ignore_errors=True)


def processar_fonte(
    fonte: str,
    ano: int,
    raiz_raw: Path,
    raiz_proc: Path,
    *,
    manifesto: Manifesto | None = None,
    sal: str | None = None,
) -> list[Path]:
    """Processa todos os membros do ZIP de ``fonte``/``ano``; devolve os Parquets escritos."""
    if fonte not in FONTES:
        raise ErroProcessamento(f"fonte sem processador: {fonte}")
    spec = FONTES[fonte]
    [alvo] = alvos(ano, [spec.zip_id or fonte])
    zip_path = raiz_raw / alvo.destino
    if not zip_path.exists():
        raise ErroProcessamento(f"{zip_path} não existe; rode `etl baixar` antes")
    ctx = Contexto(ano, sal, raiz_raw, raiz_proc)
    usa_sal = "pessoa_id" in spec.contrato.derivadas
    if usa_sal and sal and manifesto:
        _conferir_sal_do_manifesto(manifesto, Path(alvo.destino).parent.name, alvo.destino, sal)
    cross = (
        _crosswalk(raiz_raw, raiz_proc, ano) if "cd_mun_ibge" in spec.contrato.derivadas else None
    )
    raiz_proc.mkdir(parents=True, exist_ok=True)
    pasta = raiz_proc / fonte / f"ano={ano}"
    stage = pasta.with_name(pasta.name + ".tmp")
    shutil.rmtree(stage, ignore_errors=True)
    # Temporário FORA de processed/ (pasta publicável), modo 0700: o CSV traz CPF/título.
    tmp = Path(tempfile.mkdtemp(prefix="etl-"))
    nomes: list[str] = []
    geracoes: list[str] = []
    try:
        for membro in membros_dados(zip_path, spec.prefixo):
            nome = (
                "municipio_tse_ibge.parquet"
                if fonte == CROSSWALK
                else Path(membro).stem.split("_")[-1] + ".parquet"
            )
            dt = _processar_membro(spec, zip_path, membro, stage / nome, tmp, ctx, cross)
            nomes.append(nome)
            if dt:
                geracoes.append(dt)
        _publicar(stage, pasta)  # só depois de TODOS os membros validados
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    escritos = [pasta / n for n in nomes]
    if manifesto and geracoes:
        entrada = manifesto.por_caminho(alvo.destino)
        if entrada:
            impressao = impressao_do_sal(sal) if usa_sal and sal else entrada.sal_impressao
            manifesto.registrar(replace(entrada, dt_geracao=max(geracoes), sal_impressao=impressao))
    return escritos
