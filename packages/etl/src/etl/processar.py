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
from etl.tse_csv import ler_membro, membros_dados

LOG = logging.getLogger(__name__)
ELEITORADO = CONTRATOS["eleitorado_local_votacao"]
EXTERIOR = "ZZ"  # zonas do exterior não têm município IBGE
CROSSWALK = "municipio_tse_ibge"


class ErroProcessamento(RuntimeError):  # noqa: N818 - nome de domínio
    """Falha de regra de negócio no processamento (crosswalk, sal, totais de controle)."""


def hash_pessoa(cpf: str | None, titulo: str | None, sal: str) -> str | None:
    """``sha256(sal || cpf_normalizado)`` (ADR 0004); sem CPF válido cai no título.

    "Não divulgável" (``-4``, vazio, sem dígitos) não identifica ninguém → ``None``.
    """
    for bruto, minimo_digitos in ((cpf, 11), (titulo, 8)):
        if not bruto or bruto.strip().startswith("-"):
            continue
        digitos = re.sub(r"\D", "", bruto)
        if len(digitos) >= minimo_digitos:
            return hashlib.sha256(sal.encode() + digitos.encode()).hexdigest()
    return None


@dataclass(frozen=True)
class Contexto:
    """O que as regras específicas de cada fonte podem precisar."""

    ano: int
    sal: str | None


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
    sem_coord = ((pl.col("nr_latitude") == -1.0) & (pl.col("nr_longitude") == -1.0)) | (
        pl.col("sg_uf") == EXTERIOR
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
    return lf.group_by(chave).agg(
        _primeiro("nm_local_votacao"), _primeiro("ds_endereco"), _primeiro("nm_bairro"),
        _primeiro("nr_latitude"), _primeiro("nr_longitude"),
        pl.len().cast(pl.Int32).alias("qt_secoes"),
        pl.col("qt_eleitor_secao").sum(),
        pl.col("dt_geracao").max(),
    )  # fmt: skip


@dataclass(frozen=True)
class Fonte:
    """Como processar uma fonte: contrato, soma de controle e regra opcional."""

    contrato: Contrato
    controle: tuple[str, ...] = ()  # colunas inteiras cuja soma deve bater com a origem
    linhas_1a1: bool = True  # saída tem tantas linhas quanto a entrada?
    extras: tuple[str, ...] = ()
    regra: Regra | None = None


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
        regra=_agregar_locais,
    ),
}


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


def _controle(bruto: pl.LazyFrame, saida: pl.LazyFrame, fonte: Fonte, membro: str) -> None:
    """Total de controle: soma(origem) == soma(saída) e, quando 1:1, nº de linhas."""
    esperado = (
        bruto.select(pl.len().alias("__n"), *[pl.col(c).sum().alias(c) for c in fonte.controle])
        .collect()
        .row(0, named=True)
    )
    obtido = (
        saida.select(pl.len().alias("__n"), *[pl.col(c).sum().alias(c) for c in fonte.controle])
        .collect()
        .row(0, named=True)
    )
    if not fonte.linhas_1a1:
        esperado.pop("__n")
        obtido.pop("__n")
    if esperado != obtido:
        raise ErroProcessamento(
            f"{membro}: totais de controle divergem: origem {esperado} × saída {obtido}"
        )


def _processar_membro(
    nome: str, fonte: Fonte, zip_path: Path, membro: str, destino: Path, tmp: Path,
    ctx: Contexto, crosswalk: pl.LazyFrame | None,
) -> str | None:  # fmt: skip
    """Devolve o ``dt_geracao`` (máximo) do membro."""
    bruto = ler_membro(zip_path, membro, fonte.contrato, tmp, fonte.extras)
    lf = bruto
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
        _controle(bruto, saida, fonte, membro)
        os.replace(temporario, destino)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise
    ultima = pl.scan_parquet(destino).select(pl.col("dt_geracao").max()).collect().item()
    return None if ultima is None else ultima.isoformat()


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
    [alvo] = alvos(ano, [fonte])
    zip_path = raiz_raw / alvo.destino
    if not zip_path.exists():
        raise ErroProcessamento(f"{zip_path} não existe; rode `etl baixar` antes")
    ctx = Contexto(ano, sal)
    cross = (
        _crosswalk(raiz_raw, raiz_proc, ano) if "cd_mun_ibge" in spec.contrato.derivadas else None
    )
    raiz_proc.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".etl-", dir=raiz_proc))
    escritos: list[Path] = []
    geracoes: list[str] = []
    try:
        for membro in membros_dados(zip_path):
            destino = (
                raiz_proc / fonte / f"ano={ano}" / (Path(membro).stem.split("_")[-1] + ".parquet")
            )
            if fonte == CROSSWALK:
                destino = raiz_proc / fonte / f"ano={ano}" / "municipio_tse_ibge.parquet"
            dt = _processar_membro(fonte, spec, zip_path, membro, destino, tmp, ctx, cross)
            escritos.append(destino)
            if dt:
                geracoes.append(dt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if manifesto and geracoes:
        entrada = manifesto.por_caminho(alvo.destino)
        if entrada:
            manifesto.registrar(replace(entrada, dt_geracao=max(geracoes)))
    return escritos
