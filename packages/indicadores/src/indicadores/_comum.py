"""Utilitários internos compartilhados pelos módulos de indicadores (sem I/O, sem estado)."""

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


def exigir_unicidade(df: pl.DataFrame, chaves: Sequence[str], contexto: str) -> None:
    """Falha alto se houver linhas repetidas para as `chaves` (tabela não agregada)."""
    if df.select(list(chaves)).is_duplicated().any():
        raise ValueError(f"{contexto}: linhas duplicadas para as chaves {list(chaves)}")
