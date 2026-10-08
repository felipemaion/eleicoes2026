"""Casos de uso /mapa e /mapa/pontos: valores por território para o coroplético e a densidade."""

from collections.abc import Mapping, Sequence

import polars as pl
from indicadores import desempenho, espacial
from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Indicador, Nivel
from api.erros import parametro_invalido
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.escopo import selecionar_alvo
from api.servicos.grupos import Catalogo

_UNIDADE = {Indicador.PENETRACAO: "‰", Indicador.PCT_VALIDOS: "%", Indicador.VOTOS: "votos"}
_DENOMINADOR = {
    Indicador.PENETRACAO: "aptos",
    Indicador.PCT_VALIDOS: "votos_validos",
    Indicador.VOTOS: None,
}


class Detalhe(BaseModel):
    """Numerador e denominadores de um território."""

    votos: int
    aptos: int
    validos: int | None = Field(description="null no H3: não há 'válidos' por célula (§2.2).")
    taxa: float | None = Field(description="Valor do indicador; null = sem dado (denominador 0).")


class EscalaSugerida(BaseModel):
    """Sugestão de classes para a legenda (spec §8.2); o front decide a cor final."""

    tipo: str = Field(description="`sequencial` (taxas) ou `simbolo_proporcional` (absolutos).")
    paleta: str
    quebras: list[float] | None = Field(
        description="Cortes internos da legenda; null quando não há como calcular (ver `aviso`)."
    )
    aviso: str | None = Field(default=None, description="Por que `quebras` é null, se for.")
    anos: list[int] = Field(
        default_factory=list,
        description="Anos cujos valores entraram nas quebras (2022+2026 numa comparação).",
    )


class Mapa(BaseModel):
    """Corpo de GET /mapa. Chaves: IBGE (município), `IBGE-zona`, ou índice H3."""

    ano: int
    nivel: str
    indicador: str
    valores: dict[str, float | None]
    detalhes: dict[str, Detalhe]
    escala_sugerida: EscalaSugerida
    unidade: str
    denominador: str | None
    n_candidaturas: int
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ano": 2026,
                    "nivel": "municipio",
                    "indicador": "penetracao",
                    "valores": {"3550308": 73.33, "3509502": 20.0},
                    "detalhes": {
                        "3550308": {"votos": 1100, "aptos": 15000, "validos": 10500, "taxa": 73.33}
                    },
                    "escala_sugerida": {
                        "tipo": "sequencial",
                        "paleta": "viridis",
                        "quebras": [20.0, 40.0, 60.0, 70.0],
                    },
                    "unidade": "‰",
                    "denominador": "aptos",
                    "n_candidaturas": 2,
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


Linha = tuple[str, int, int, int | None]  # (chave, votos, aptos, válidos)
_CLASSES = 5  # quintis; quebras_comuns reduz se os dados empatarem


def quebras_da_escala(
    linhas_por_ano: Mapping[int, Sequence[Linha]], indicador: Indicador
) -> tuple[list[float] | None, str | None]:
    """Cortes da legenda comuns a todos os anos (spec §8.2), sem unidades de n baixo (§1.4).

    Delega a `indicadores.espacial.quebras_comuns`. Dados insuficientes (< 2k valores ou sem
    variação) viram `(None, aviso)`: o chamador explica ao usuário, nunca devolve lista inventada.
    """
    tabelas = {ano: _tabela_escala(linhas, indicador) for ano, linhas in linhas_por_ano.items()}
    try:
        return espacial.quebras_comuns(tabelas, k=_CLASSES), None
    except ValueError as erro:
        return None, f"sem base para quebras comuns: {erro}"


def _tabela_escala(linhas: Sequence[Linha], indicador: Indicador) -> pl.DataFrame:
    """`valor` (taxa do indicador) e `n_baixo` por território, pela biblioteca de indicadores."""
    quadro = _quadro(linhas)
    calculado = desempenho.penetracao(desempenho.pct_validos(quadro))
    total_aptos = int(quadro["aptos"].sum())
    # Taxa de referência = penetração do recorte inteiro (proporção), base do esperado (§1.4).
    taxa_ref = int(quadro["votos"].sum()) / total_aptos if total_aptos else None
    calculado = calculado.with_columns(pl.lit(taxa_ref, dtype=pl.Float64).alias("taxa_referencia"))
    coluna = {Indicador.PENETRACAO: "penetracao", Indicador.PCT_VALIDOS: "pct_validos"}[indicador]
    return espacial.n_baixo(calculado).select(pl.col(coluna).alias("valor"), "n_baixo")


def escala_comum(
    linhas_por_ano: Mapping[int, Sequence[Linha]], indicador: Indicador
) -> EscalaSugerida:
    """Escala do indicador para os anos dados; absolutos viram símbolo proporcional."""
    if indicador is Indicador.VOTOS:
        return EscalaSugerida(
            tipo="simbolo_proporcional",
            paleta="um_matiz",
            quebras=[],
            anos=sorted(linhas_por_ano),
        )
    quebras, aviso = quebras_da_escala(linhas_por_ano, indicador)
    return EscalaSugerida(
        tipo="sequencial",
        paleta="viridis",
        quebras=quebras,
        aviso=aviso,
        anos=sorted(linhas_por_ano),
    )


def _outro_lado(catalogo: Catalogo, comparacao_id: str, grupo_id: str | None) -> tuple[str, int]:
    """Grupo e ano do outro lado da comparação (`de` ↔ `para`)."""
    comp = catalogo.comparacao(comparacao_id)
    if grupo_id not in (comp.de, comp.para):
        raise parametro_invalido(
            "comparacao_sem_grupo",
            f"com 'comparacao', 'grupo' deve ser '{comp.de}' ou '{comp.para}'",
        )
    outro = comp.para if grupo_id == comp.de else comp.de
    return outro, catalogo.grupo(outro).ano


def _coletar(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    nivel: Nivel,
    grupo_id: str | None,
    sq_candidato: int | None,
) -> tuple[list[Candidatura], list[Linha]]:
    """Candidaturas do recorte e linhas (chave, votos, aptos, válidos) por território."""
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    sqs = [c.sq_candidato for c in alvo]
    if nivel is Nivel.H3:
        assert uf is not None  # noqa: S101 - exigido por quem chama
        return alvo, [(c.h3, c.votos, c.aptos, None) for c in repo.votos_h3(ano, sqs, uf=uf)]
    por_zona = nivel is Nivel.ZONA
    votos = {
        (v.cd_mun_ibge, v.nr_zona): v.votos
        for v in repo.votos_territorio(ano, sqs, por_zona=por_zona, uf=uf)
    }
    base = repo.base_eleitoral(ano, cargo, por_zona=por_zona, uf=uf)
    vistos = {(b.cd_mun_ibge, b.nr_zona) for b in base}
    linhas: list[Linha] = [
        (
            _chave(b.cd_mun_ibge, b.nr_zona),
            votos.get((b.cd_mun_ibge, b.nr_zona), 0),
            b.aptos,
            b.validos,
        )
        for b in base
    ]
    # Voto sem base eleitoral: aparece como "sem dado" (aptos 0 → null), não some.
    linhas += [(_chave(m, z), n, 0, 0) for (m, z), n in votos.items() if (m, z) not in vistos]
    return alvo, linhas


def montar_mapa(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    nivel: Nivel,
    indicador: Indicador,
    grupo_id: str | None,
    sq_candidato: int | None,
    comparacao: str | None = None,
) -> Mapa:
    """Indicador por território; com aptos e sem voto = 0, sem aptos = null (nunca inf).

    Com `comparacao`, a escala usa quebras comuns ao ano pedido e ao do outro lado dela.
    """
    if nivel is not Nivel.MUNICIPIO and uf is None:
        raise parametro_invalido("uf_obrigatoria", f"nivel={nivel.value} exige 'uf'")
    if nivel is Nivel.H3 and indicador is Indicador.PCT_VALIDOS:
        raise parametro_invalido(
            "indicador_indisponivel", "pct_validos não existe no H3; use penetracao ou votos"
        )
    if comparacao is not None and sq_candidato is not None:
        raise parametro_invalido("comparacao_com_candidato", "'comparacao' vale só para 'grupo'")
    outro = _outro_lado(catalogo, comparacao, grupo_id) if comparacao else None
    alvo, linhas = _coletar(
        repo,
        catalogo,
        ano=ano,
        cargo=cargo,
        uf=uf,
        nivel=nivel,
        grupo_id=grupo_id,
        sq_candidato=sq_candidato,
    )
    por_ano = {ano: linhas}
    if outro is not None:
        grupo_outro, ano_outro = outro
        por_ano[ano_outro] = _coletar(
            repo,
            catalogo,
            ano=ano_outro,
            cargo=cargo,
            uf=uf,
            nivel=nivel,
            grupo_id=grupo_outro,
            sq_candidato=None,
        )[1]
    detalhes = _detalhes(indicador, linhas)
    return Mapa(
        ano=ano,
        nivel=nivel.value,
        indicador=indicador.value,
        valores={k: d.taxa for k, d in detalhes.items()},
        detalhes=detalhes,
        escala_sugerida=escala_comum(por_ano, indicador),
        unidade=_UNIDADE[indicador],
        denominador=_DENOMINADOR[indicador],
        n_candidaturas=len(alvo),
        dt_geracao=repo.dt_geracao(),
    )


def _quadro(linhas: Sequence[Linha]) -> pl.DataFrame:
    return pl.DataFrame(
        list(linhas),
        schema={"chave": pl.String, "votos": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64},
        orient="row",
    )


def _detalhes(indicador: Indicador, linhas: Sequence[Linha]) -> dict[str, Detalhe]:
    """Taxas de todos os territórios de uma vez, pela biblioteca de indicadores."""
    calculado = desempenho.penetracao(desempenho.pct_validos(_quadro(linhas)))
    coluna = {
        Indicador.PENETRACAO: "penetracao",
        Indicador.PCT_VALIDOS: "pct_validos",
        Indicador.VOTOS: "votos",
    }[indicador]
    return {
        r["chave"]: Detalhe(
            votos=r["votos"],
            aptos=r["aptos"],
            validos=r["validos"],
            taxa=None if r[coluna] is None else float(r[coluna]),
        )
        for r in calculado.to_dicts()
    }


def _chave(cd_mun_ibge: int, nr_zona: int | None) -> str:
    return str(cd_mun_ibge) if nr_zona is None else f"{cd_mun_ibge}-{nr_zona}"


class Ponto(BaseModel):
    """Local de votação."""

    lat: float
    lon: float
    votos: int


class Pontos(BaseModel):
    """Corpo de GET /mapa/pontos (densidade de votos por local)."""

    ano: int
    total: int = Field(description="Locais com voto no recorte.")
    limite: int
    offset: int
    truncado: bool = Field(description="Há mais páginas além desta.")
    pontos: list[Ponto]
    dt_geracao: str


def montar_pontos(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str,
    grupo_id: str | None,
    sq_candidato: int | None,
    limite: int,
    offset: int,
) -> Pontos:
    """Locais de votação com voto, mais votados primeiro, paginados."""
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    total, linhas = repo.pontos(
        ano, [c.sq_candidato for c in alvo], uf=uf, limite=limite, offset=offset
    )
    return Pontos(
        ano=ano,
        total=total,
        limite=limite,
        offset=offset,
        truncado=offset + len(linhas) < total,
        pontos=[Ponto(lat=p.lat, lon=p.lon, votos=p.votos) for p in linhas],
        dt_geracao=repo.dt_geracao(),
    )
