"""Evolução 2022 → 2026 (spec §5): Δ penetração, swing, retenção, ganho por AMC,
sobreposição de redutos e normalização por candidato / "mesmos candidatos".

Unidade espacial: AMC (município IBGE com desmembramentos agregados ao de origem) ou H3.
Zona **nunca** (rezoneamento, ADR 0003). Sempre mesmo cargo e 1º turno.
"""

import math
from collections.abc import Sequence

import polars as pl

from indicadores._comum import (
    exigir_colunas,
    exigir_unicidade,
    expr_pct_validos,
    expr_penetracao,
    razao,
)

_CONTAGENS = ("aptos", "validos", "votos")
CD_CARGO_SENADOR = 5
"""`CD_CARGO` do Senado no TSE. Fora da evolução: 2022 elegeu 1 vaga, 2026 elege 2 (§1.8)."""
LIMIAR_REDUTO = 2.0
"""LQ a partir do qual uma AMC é reduto (spec §5.2)."""


def agregar_amc(df: pl.DataFrame, amc: pl.DataFrame, por: Sequence[str] = ()) -> pl.DataFrame:
    """Soma `aptos`, `validos`, `votos` dos municípios em cada AMC (antes de qualquer taxa).

    Args:
        df: `por…, cd_mun_ibge, aptos, validos, votos`.
        amc: `cd_mun_ibge → amc` (uma linha por município; produzida pelo `dados`).

    Raises:
        ValueError: município sem AMC ou município repetido na tabela AMC.
    """
    exigir_colunas(df, [*por, "cd_mun_ibge", *_CONTAGENS], "agregar_amc")
    exigir_colunas(amc, ["cd_mun_ibge", "amc"], "agregar_amc(amc)")
    exigir_unicidade(amc, ["cd_mun_ibge"], "agregar_amc(amc)")
    ligado = df.join(amc.select("cd_mun_ibge", "amc"), on="cd_mun_ibge", how="left")
    sem_amc = ligado.filter(pl.col("amc").is_null())["cd_mun_ibge"].unique().to_list()
    if sem_amc:
        raise ValueError(f"agregar_amc: municípios sem AMC {sorted(sem_amc)[:10]}")
    return ligado.group_by([*por, "amc"]).agg(pl.col(c).sum() for c in _CONTAGENS)


def evolucao(
    ano_2022: pl.DataFrame,
    ano_2026: pl.DataFrame,
    amc: pl.DataFrame,
    por: Sequence[str] = (),
    *,
    cd_cargo: int,
) -> pl.DataFrame:
    """Δ penetração, swing, retenção e ganho por AMC (spec §5.1).

    `delta_penetracao = pen_2026 − pen_2022` (‰, âncora); `swing_pp = %válidos_2026 −
    %válidos_2022` (p.p.); `retencao = votos_2026 / votos_2022` (`null` se 0);
    `ganho_absoluto = votos_2026 − votos_2022` (só símbolos, nunca coroplético).

    AMC presente num ano só (p. ex. entidade sem linha num município, ou município fora da
    base de um dos anos): as colunas `*_<ano ausente>` e **todas** as diferenças
    (`delta_penetracao`, `swing_pp`, `retencao`, `ganho_absoluto`) ficam `null` — ausência é
    "sem dado", não zero (zero votos com eleitorado vem como linha com `votos = 0`).

    Args:
        ano_2022, ano_2026: `por…, cd_mun_ibge, aptos, validos, votos` (mesmo cargo, 1º turno).
        amc: tabela `cd_mun_ibge → amc` que cobre os municípios dos dois anos.
        cd_cargo: cargo comparado (código TSE); obrigatório para recusar o Senado.

    Raises:
        ValueError: Senado (`cd_cargo = 5`) ou município sem AMC.
    """
    if cd_cargo == CD_CARGO_SENADOR:
        raise ValueError(
            "evolucao: Senado não entra em evolução (1 vaga em 2022, 2 em 2026; spec §1.8)"
        )
    chaves = [*por, "amc"]
    lados = []
    for ano, df in (("2022", ano_2022), ("2026", ano_2026)):
        agregado = agregar_amc(df, amc, por)
        lados.append(
            agregado.with_columns(
                expr_penetracao().alias("penetracao"), expr_pct_validos().alias("pct_validos")
            ).rename({c: f"{c}_{ano}" for c in (*_CONTAGENS, "penetracao", "pct_validos")})
        )
    juntos = lados[0].join(lados[1], on=chaves, how="full", coalesce=True)
    return juntos.with_columns(
        (pl.col("penetracao_2026") - pl.col("penetracao_2022")).alias("delta_penetracao"),
        (pl.col("pct_validos_2026") - pl.col("pct_validos_2022")).alias("swing_pp"),
        razao(pl.col("votos_2026"), pl.col("votos_2022")).alias("retencao"),
        (pl.col("votos_2026") - pl.col("votos_2022")).alias("ganho_absoluto"),
    ).sort(chaves)


def _postos(valores: list[float]) -> list[float]:
    ordem = sorted(range(len(valores)), key=lambda i: valores[i])
    postos = [0.0] * len(valores)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and valores[ordem[j + 1]] == valores[ordem[i]]:
            j += 1
        medio = (i + j) / 2 + 1  # posto médio dos empates
        for k in range(i, j + 1):
            postos[ordem[k]] = medio
        i = j + 1
    return postos


def spearman(a: pl.Series, b: pl.Series) -> float | None:
    """ρ de Spearman com postos médios nos empates; pares com nulo saem (spec §5.2).

    Menos de 2 pares ou variância zero → `None`.
    """
    pares = [(x, y) for x, y in zip(a.to_list(), b.to_list(), strict=True) if None not in (x, y)]
    if len(pares) < 2:
        return None
    ra = _postos([float(x) for x, _ in pares])
    rb = _postos([float(y) for _, y in pares])
    media = (len(pares) + 1) / 2  # média dos postos 1..n, inclusive com empates
    cov = sum((x - media) * (y - media) for x, y in zip(ra, rb, strict=True))
    var_a = sum((x - media) ** 2 for x in ra)
    var_b = sum((y - media) ** 2 for y in rb)
    if var_a == 0 or var_b == 0:
        return None
    return cov / math.sqrt(var_a * var_b)


def sobreposicao_redutos(
    df: pl.DataFrame, unidade: str = "amc", limiar: float = LIMIAR_REDUTO
) -> pl.DataFrame:
    """Spearman entre LQ 2022 e 2026 e Jaccard dos redutos (spec §5.2). Uma linha.

    Reduto = `LQ ≥ limiar` e `n_baixo = false`. `jaccard = |R22 ∩ R26| / |R22 ∪ R26|`
    (`null` sem reduto). Spearman e não Pearson: o LQ é muito assimétrico.

    Args:
        df: `unidade, lq_2022, lq_2026, n_baixo` (n baixo em qualquer dos anos).
    """
    exigir_colunas(df, [unidade, "lq_2022", "lq_2026", "n_baixo"], "sobreposicao_redutos")
    confiavel = ~pl.col("n_baixo")
    redutos = {
        ano: sorted(df.filter(confiavel & (pl.col(f"lq_{ano}") >= limiar))[unidade].to_list())
        for ano in ("2022", "2026")
    }
    uniao = set(redutos["2022"]) | set(redutos["2026"])
    jaccard = len(set(redutos["2022"]) & set(redutos["2026"])) / len(uniao) if uniao else None
    tipo_lista = pl.List(df.schema[unidade])
    return pl.DataFrame(
        {
            "spearman": pl.Series([spearman(df["lq_2022"], df["lq_2026"])], dtype=pl.Float64),
            "redutos_2022": pl.Series([redutos["2022"]], dtype=tipo_lista),
            "redutos_2026": pl.Series([redutos["2026"]], dtype=tipo_lista),
            "jaccard": pl.Series([jaccard], dtype=pl.Float64),
        }
    )


def por_candidato(df: pl.DataFrame) -> pl.DataFrame:
    """Normalização por candidatura apta (spec §5.3).

    Acrescenta `votos_por_candidato = votos / n`, `penetracao` (‰) e
    `penetracao_por_candidato = penetracao / n`; `n_candidatos = 0` → `null`.

    Args:
        df: `votos`, `aptos`, `n_candidatos` (aptas do grupo no cargo e recorte; ver
            `grupos.n_candidatos`).
    """
    exigir_colunas(df, ["votos", "aptos", "n_candidatos"], "por_candidato")
    n = pl.col("n_candidatos")
    return df.with_columns(
        razao(pl.col("votos"), n).alias("votos_por_candidato"),
        expr_penetracao().alias("penetracao"),
    ).with_columns(razao(pl.col("penetracao"), n).alias("penetracao_por_candidato"))


def mesmos_candidatos(ano_2022: pl.DataFrame, ano_2026: pl.DataFrame) -> pl.DataFrame:
    """Recorte "mesmos candidatos": interseção de `pessoa_id` entre os anos (spec §5.3).

    Saída (uma linha): `pessoa_ids` (ordenados), `n_2022`, `n_2026` (tamanho de cada grupo,
    mostrado sempre), `votos_2022`, `votos_2026` (só os comuns) e `retencao`.

    Args:
        ano_2022, ano_2026: `pessoa_id`, `votos` (uma linha por pessoa, mesmo cargo).
    """
    for nome, df in (("2022", ano_2022), ("2026", ano_2026)):
        exigir_colunas(df, ["pessoa_id", "votos"], f"mesmos_candidatos({nome})")
        exigir_unicidade(df, ["pessoa_id"], f"mesmos_candidatos({nome})")
    comuns = sorted(set(ano_2022["pessoa_id"].to_list()) & set(ano_2026["pessoa_id"].to_list()))
    v22 = int(ano_2022.filter(pl.col("pessoa_id").is_in(comuns))["votos"].sum())
    v26 = int(ano_2026.filter(pl.col("pessoa_id").is_in(comuns))["votos"].sum())
    return pl.DataFrame(
        {
            "pessoa_ids": pl.Series([comuns], dtype=pl.List(ano_2022.schema["pessoa_id"])),
            "n_2022": [ano_2022.height],
            "n_2026": [ano_2026.height],
            "votos_2022": [v22],
            "votos_2026": [v26],
            "retencao": pl.Series([v26 / v22 if v22 else None], dtype=pl.Float64),
        }
    )
