"""Utilitários internos compartilhados pelos módulos de indicadores (sem I/O, sem estado)."""

import math
from collections.abc import Iterable, Sequence

import polars as pl

LIMIAR_N_BAIXO = 20.0
"""Eventos esperados abaixo dos quais uma taxa é instável (critério NCHS/CDC; spec §1.4)."""


def razao(numerador: pl.Expr, denominador: pl.Expr) -> pl.Expr:
    """`numerador / denominador` em Float64, ou `null` se o denominador for 0 ou nulo.

    Convenção da spec (§0): indefinido é `null`, nunca `0`, `inf` ou `NaN`.
    """
    return (
        pl.when(denominador.is_null() | (denominador == 0))
        .then(pl.lit(None, dtype=pl.Float64))
        .otherwise(numerador.cast(pl.Float64) / denominador.cast(pl.Float64))
    )


def expr_penetracao(votos: str = "votos", aptos: str = "aptos") -> pl.Expr:
    """Penetração em ‰ dos aptos: `1000 × votos / aptos` (spec §2.3); `aptos = 0` → `null`."""
    return 1000 * razao(pl.col(votos), pl.col(aptos))


def expr_pct_validos(votos: str = "votos", validos: str = "validos") -> pl.Expr:
    """% dos válidos: `100 × votos / validos` (spec §2.2); `validos = 0` → `null`."""
    return 100 * razao(pl.col(votos), pl.col(validos))


def sobre(expr: pl.Expr, por: Sequence[str]) -> pl.Expr:
    """Aplica `expr` como janela sobre `por`, ou sobre a tabela inteira se `por` for vazio."""
    return expr.over(list(por)) if por else expr


def exigir_colunas(df: pl.DataFrame, colunas: Iterable[str], contexto: str) -> None:
    """Falha alto se `df` não tiver todas as `colunas` exigidas por `contexto`."""
    ausentes = [c for c in colunas if c not in df.columns]
    if ausentes:
        raise ValueError(f"{contexto}: colunas ausentes {ausentes}")


def exigir_valor_unico(df: pl.DataFrame, coluna: str, regra: str, contexto: str) -> None:
    """Falha alto se `coluna` existir em `df` com mais de um valor (p. ex. dois turnos).

    Somar turnos ou cargos dupla-contaria o eleitor (spec §0, §1.3); ausência da coluna é
    aceita — o chamador já filtrou o recorte.
    """
    if coluna in df.columns and df[coluna].n_unique() > 1:
        raise ValueError(
            f"{contexto}: {regra} ({coluna} com valores {sorted(df[coluna].unique().to_list())})"
        )


def exigir_unicidade(df: pl.DataFrame, chaves: Sequence[str], contexto: str) -> None:
    """Falha alto se houver linhas repetidas para as `chaves` (tabela não agregada)."""
    if df.select(list(chaves)).is_duplicated().any():
        raise ValueError(f"{contexto}: linhas duplicadas para as chaves {list(chaves)}")


def postos(valores: Sequence[float]) -> list[float]:
    """Postos 1..n com posto médio nos empates (base do ρ de Spearman)."""
    ordem = sorted(range(len(valores)), key=valores.__getitem__)
    resultado = [0.0] * len(valores)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and valores[ordem[j + 1]] == valores[ordem[i]]:
            j += 1
        medio = (i + j) / 2 + 1  # posto médio dos empates
        for k in range(i, j + 1):
            resultado[ordem[k]] = medio
        i = j + 1
    return resultado


def spearman_listas(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """ρ de Spearman (Spearman 1904) = Pearson dos postos médios; iguais ao `scipy.stats.spearmanr`.

    Menos de 2 pares ou variância zero em um dos lados → `None` (indefinido, spec §0).
    """
    if len(xs) != len(ys):
        raise ValueError("spearman: listas de tamanhos diferentes")
    if len(xs) < 2:
        return None
    rx, ry = postos(xs), postos(ys)
    media = (len(xs) + 1) / 2  # média dos postos 1..n, inclusive com empates
    cov = sum((x - media) * (y - media) for x, y in zip(rx, ry, strict=True))
    var_x = sum((x - media) ** 2 for x in rx)
    var_y = sum((y - media) ** 2 for y in ry)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)
