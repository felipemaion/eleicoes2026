"""Conferência dos números publicados contra fontes oficiais independentes (T-A04).

Funções puras: recebem o JSON de divulgação já lido (dict) ou DataFrames, nunca fazem I/O. A rede
e a leitura de arquivos ficam em `packages/indicadores/scripts/conferir.py`.

Fontes independentes do ETL (ver docs/metodologia/conferencia.md):
- 2026: JSON de divulgação do resultados.tse.jus.br (`<uf>-c<cargo>-e<eleicao>-u.json`), o canal
  que o TSE usa para divulgar a totalização — outro produto, não o CSV de dados abertos.
- 2022: o JSON de divulgação foi retirado do ar; usa-se `votacao_secao` (voto por seção e
  votável) e `detalhe_votacao_secao`, agregados do zero — outra granularidade e outro arquivo
  que não o `*_munzona` lido pelo ETL.
"""

from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl

from indicadores._comum import exigir_colunas, exigir_unicidade

CARGOS_PROPORCIONAIS = (6, 7, 8)
"""Dep. federal, estadual, distrital: número de 2 dígitos é voto de legenda."""

VOTAVEL_BRANCO = 95
VOTAVEL_NULO = 96
VOTAVEIS_RESERVADOS = (97, 98, 99)
"""Fora da numeração de partidos e sem uso conhecido no `votacao_secao`: se aparecerem, falha."""

_MEDIDAS_TOTAIS = (
    "aptos",
    "comparecimento",
    "votos_validos",
    "votos_nominais_validos",
    "votos_legenda",
    "votos_brancos",
    "votos_nulos",
)


def _int(valor: str | None) -> int | None:
    return None if valor in (None, "") else int(valor)


def _cargo_unico(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    cargos = doc.get("carg") or []
    if len(cargos) != 1:
        raise ValueError(f"divulgação: esperado um cargo por arquivo, veio {len(cargos)}")
    cargo: Mapping[str, Any] = cargos[0]
    return cargo


def _uf_cargo(doc: Mapping[str, Any]) -> tuple[str, int]:
    return str(doc["cdabr"]).upper(), int(_cargo_unico(doc)["cd"])


def _partidos(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [p for agr in _cargo_unico(doc)["agr"] for p in agr["par"]]


def divulgacao_totais(doc: Mapping[str, Any]) -> pl.DataFrame:
    """Totais da circunscrição × cargo no JSON de divulgação (uma linha).

    `aptos = e.te`, `comparecimento = e.c`, `votos_validos = v.vv` (= nominais + legenda),
    `votos_nominais_validos = v.vnom`, `votos_legenda = v.vl` (null no majoritário, onde não
    existe), `votos_brancos = v.vb`, `votos_nulos = v.tvn` (nulos + nulos técnicos).

    Raises:
        ValueError: arquivo com zero ou mais de um cargo.
    """
    uf, cargo = _uf_cargo(doc)
    e, v = doc["e"], doc["v"]
    valores = {
        "aptos": e["te"],
        "comparecimento": e["c"],
        "votos_validos": v["vv"],
        "votos_nominais_validos": v["vnom"],
        "votos_legenda": v.get("vl"),
        "votos_brancos": v["vb"],
        "votos_nulos": v["tvn"],
    }
    return pl.DataFrame(
        [{"sg_uf": uf, "cd_cargo": cargo, **{k: _int(x) for k, x in valores.items()}}],
        schema={
            "sg_uf": pl.String,
            "cd_cargo": pl.Int64,
            **dict.fromkeys(_MEDIDAS_TOTAIS, pl.Int64),
        },
    )


def divulgacao_candidatos(doc: Mapping[str, Any]) -> pl.DataFrame:
    """Candidatos do JSON de divulgação: `votos = vap`, `destinacao = dvt`, `situacao = st`.

    `vap` é o total de votos nominais apurados para o número do candidato, **qualquer que seja
    a destinação** — corresponde a `Σ qt_votos_nominais` do `votacao_candidato_munzona` e só é
    igual aos nominais válidos quando `destinacao = "Válido"`.
    """
    uf, cargo = _uf_cargo(doc)
    linhas = [
        {
            "sg_uf": uf,
            "cd_cargo": cargo,
            "sq_candidato": int(c["sqcand"]),
            "nr_candidato": int(c["n"]),
            "nr_partido": int(p["n"]),
            "destinacao": c["dvt"],
            "situacao": c.get("st"),
            "votos": int(c["vap"]),
        }
        for p in _partidos(doc)
        for c in p["cand"]
    ]
    return pl.DataFrame(
        linhas,
        schema={
            "sg_uf": pl.String,
            "cd_cargo": pl.Int64,
            "sq_candidato": pl.Int64,
            "nr_candidato": pl.Int64,
            "nr_partido": pl.Int64,
            "destinacao": pl.String,
            "situacao": pl.String,
            "votos": pl.Int64,
        },
    )


def divulgacao_partidos(doc: Mapping[str, Any]) -> pl.DataFrame:
    """Partidos do JSON: `votos_nominais = tvtn`, `votos_legenda = tvtl` (null no majoritário).

    `tvtn` soma o `vap` dos candidatos do partido; `tvtl` é a legenda válida (digitada +
    convertida, CE art. 175 §4º).
    """
    uf, cargo = _uf_cargo(doc)
    linhas = [
        {
            "sg_uf": uf,
            "cd_cargo": cargo,
            "nr_partido": int(p["n"]),
            "sg_partido": p["sg"],
            "votos_nominais": _int(p.get("tvtn")),
            "votos_legenda": _int(p.get("tvtl")),
        }
        for p in _partidos(doc)
    ]
    return pl.DataFrame(
        linhas,
        schema={
            "sg_uf": pl.String,
            "cd_cargo": pl.Int64,
            "nr_partido": pl.Int64,
            "sg_partido": pl.String,
            "votos_nominais": pl.Int64,
            "votos_legenda": pl.Int64,
        },
    )


def classificar_votavel(secao: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `tipo_votavel` ∈ {nominal, legenda, branco, nulo} ao `votacao_secao`.

    95 = branco, 96 = nulo. Em cargo proporcional (6, 7, 8) número de 2 dígitos é legenda; no
    majoritário o número de 2 dígitos é o do candidato (governador, presidente).

    Raises:
        ValueError: código 97–99 (sem significado conhecido) — falha em vez de chutar. Note
            que 90 é número de partido (PROS em 2022), não código especial.
    """
    exigir_colunas(secao, ["cd_cargo", "nr_votavel"], "classificar_votavel")
    nr = pl.col("nr_votavel")
    especiais = secao.filter(nr.is_in(VOTAVEIS_RESERVADOS))
    if especiais.height:
        codigos = sorted(set(especiais["nr_votavel"].to_list()))
        raise ValueError(f"classificar_votavel: nr_votavel especial desconhecido {codigos}")
    return secao.with_columns(
        pl.when(nr == VOTAVEL_BRANCO)
        .then(pl.lit("branco"))
        .when(nr == VOTAVEL_NULO)
        .then(pl.lit("nulo"))
        .when((nr < 100) & pl.col("cd_cargo").is_in(CARGOS_PROPORCIONAIS))
        .then(pl.lit("legenda"))
        .otherwise(pl.lit("nominal"))
        .alias("tipo_votavel")
    )


def _longo(df: pl.DataFrame, chaves: list[str], medidas: list[str], nome: str) -> pl.DataFrame:
    return df.unpivot(
        index=chaves, on=medidas, variable_name="medida", value_name=nome
    ).with_columns(pl.col(nome).cast(pl.Float64))


def comparar(
    nosso: pl.DataFrame,
    fonte: pl.DataFrame,
    chaves: Sequence[str],
    tolerancia: float = 0,
) -> pl.DataFrame:
    """Compara medida a medida: `diferenca = nosso − fonte`, `diferenca_pct = 100·dif/fonte`.

    Entradas largas com as mesmas colunas de medida (todas as não-chave). Saída longa:
    `chaves…, medida, nosso, fonte, diferenca, diferenca_pct, situacao`, com
    `situacao ∈ {confere, diverge, so_nosso, so_fonte}` (`|dif| ≤ tolerancia` confere).
    Medida nula numa linha da fonte (ex.: legenda no majoritário) não é comparada nessa linha.
    `fonte = 0` → `diferenca_pct` nulo.

    Raises:
        ValueError: medidas diferentes entre os lados ou chaves duplicadas.
    """
    chaves = list(chaves)
    for df, lado in ((nosso, "nosso"), (fonte, "fonte")):
        exigir_colunas(df, chaves, f"comparar ({lado})")
        exigir_unicidade(df, chaves, f"comparar ({lado}): chaves duplicadas")
    medidas = sorted(c for c in nosso.columns if c not in chaves)
    medidas_fonte = sorted(c for c in fonte.columns if c not in chaves)
    if medidas != medidas_fonte:
        raise ValueError(f"comparar: medidas diferentes — nosso {medidas}, fonte {medidas_fonte}")

    lado_fonte = _longo(fonte, chaves, medidas, "fonte")
    nao_publicadas = lado_fonte.filter(pl.col("fonte").is_null()).select([*chaves, "medida"])
    juntos = (
        _longo(nosso, chaves, medidas, "nosso")
        .join(nao_publicadas, on=[*chaves, "medida"], how="anti", nulls_equal=True)
        .join(
            lado_fonte.filter(pl.col("fonte").is_not_null()),
            on=[*chaves, "medida"],
            how="full",
            coalesce=True,
            nulls_equal=True,
        )
    )
    return (
        juntos.with_columns((pl.col("nosso") - pl.col("fonte")).alias("diferenca"))
        .with_columns(
            pl.when(pl.col("fonte") != 0)
            .then(100 * pl.col("diferenca") / pl.col("fonte"))
            .otherwise(None)
            .alias("diferenca_pct"),
            pl.when(pl.col("nosso").is_null())
            .then(pl.lit("so_fonte"))
            .when(pl.col("fonte").is_null())
            .then(pl.lit("so_nosso"))
            .when(pl.col("diferenca").abs() <= tolerancia)
            .then(pl.lit("confere"))
            .otherwise(pl.lit("diverge"))
            .alias("situacao"),
        )
        .select([*chaves, "medida", "nosso", "fonte", "diferenca", "diferenca_pct", "situacao"])
        .sort([*chaves, "medida"])
    )
