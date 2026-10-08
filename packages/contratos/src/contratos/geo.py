"""Contrato da tabela ``municipios`` (IBGE + crosswalk TSE + AMC)."""

from __future__ import annotations

import polars as pl

from contratos.modelo import Contrato

MUNICIPIOS = Contrato(
    nome="municipios",
    colunas={
        "cd_mun_ibge": pl.Int32, "cd_mun_tse": pl.Int32, "sg_uf": pl.Utf8,
        "nm_municipio": pl.Utf8, "area_km2": pl.Float64, "cd_amc": pl.Int32,
    },
    chave=("cd_mun_ibge",),
    nao_nulas=("cd_mun_ibge", "cd_mun_tse", "sg_uf", "nm_municipio", "area_km2", "cd_amc"),
    faixas={"area_km2": (0.0, 2_000_000.0)},
    derivadas=frozenset({"cd_amc", "area_km2"}),
)  # fmt: skip
