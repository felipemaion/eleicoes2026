"""Contrato de um Parquet: colunas, tipos, chave única, obrigatórias e faixas."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl


class ContratoViolado(ValueError):  # noqa: N818 - nome de domínio, não sufixo Error
    """O dado não respeita o contrato; o Parquet não deve ser escrito."""


@dataclass(frozen=True)
class Contrato:
    """Descrição declarativa de um dataset processado.

    Os nomes são os do TSE em minúsculas (``QT_APTOS`` → ``qt_aptos``), salvo colunas
    derivadas pelo ETL (``cd_mun_ibge``, ``pessoa_id``), listadas em ``derivadas``.
    """

    nome: str
    colunas: dict[str, pl.DataType | type[pl.DataType]]
    chave: tuple[str, ...]
    nao_nulas: tuple[str, ...] = ()
    faixas: dict[str, tuple[float, float]] = field(default_factory=dict)
    derivadas: frozenset[str] = frozenset()
    # coluna de domínio → nome no CSV do TSE, quando não for ``nome.upper()``
    origem: dict[str, str] = field(default_factory=dict)

    def schema(self) -> dict[str, pl.DataType | type[pl.DataType]]:
        """Schema polars esperado (ordem das colunas incluída)."""
        return dict(self.colunas)


def validar(dados: pl.DataFrame | pl.LazyFrame, contrato: Contrato) -> None:
    """Levanta :class:`ContratoViolado` se ``dados`` violar ``contrato``.

    Confere colunas (sem faltar nem sobrar), tipos, nulos em obrigatórias, faixas e
    unicidade da chave. Em ``LazyFrame`` só materializa agregados, não o dado.
    """
    lf = dados.lazy()
    real = lf.collect_schema()
    esperado = contrato.schema()
    if set(real) != set(esperado):
        faltam = sorted(set(esperado) - set(real))
        sobram = sorted(set(real) - set(esperado))
        raise ContratoViolado(
            f"{contrato.nome}: colunas diferentes (faltam {faltam}, sobram {sobram})"
        )
    for col, tipo in esperado.items():
        if real[col] != tipo:
            raise ContratoViolado(f"{contrato.nome}: tipo de {col} é {real[col]}, esperado {tipo}")

    aggs: list[pl.Expr] = [pl.len().alias("__n")]
    aggs += [pl.col(c).null_count().alias(f"__nulo_{c}") for c in contrato.nao_nulas]
    for c in contrato.faixas:
        aggs += [pl.col(c).min().alias(f"__min_{c}"), pl.col(c).max().alias(f"__max_{c}")]
    aggs.append(pl.struct(list(contrato.chave)).n_unique().alias("__chaves"))
    r = lf.select(aggs).collect().row(0, named=True)

    for c in contrato.nao_nulas:
        if r[f"__nulo_{c}"]:
            raise ContratoViolado(f"{contrato.nome}: {r[f'__nulo_{c}']} nulo(s) em {c}")
    for c, (lo, hi) in contrato.faixas.items():
        mn, mx = r[f"__min_{c}"], r[f"__max_{c}"]
        if (mn is not None and mn < lo) or (mx is not None and mx > hi):
            raise ContratoViolado(
                f"{contrato.nome}: {c} fora da faixa [{lo}, {hi}] (min={mn}, max={mx})"
            )
    if r["__chaves"] != r["__n"]:
        raise ContratoViolado(
            f"{contrato.nome}: {r['__n'] - r['__chaves']} chave(s) duplicada(s) em {contrato.chave}"
        )
