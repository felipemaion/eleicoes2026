"""Critério da lista MBL 2022: reproduzido do ``consulta_cand`` via ``pessoa_id`` (T-D06).

A lista de referência (``data/reference/mbl_2022.csv``) é manual; este módulo prova que ela
decorre de um critério objetivo e detecta deriva (por exemplo, sais de ``pessoa_id`` diferentes).
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

NR_PARTIDO_MISSAO = 14


def candidaturas_mbl_2022(cand: pl.DataFrame, indicados: Iterable[int]) -> pl.DataFrame:
    """Candidaturas de 2022 do grupo MBL: indicados + pessoas do Missão 2026 que disputaram 2022.

    ``indicados`` são os ``sq_candidato`` de 2022 escolhidos à mão (não deriváveis do dado).
    Uma candidatura por pessoa: quando ela teve dois registros em 2022, vale o que tem
    resultado de urna (``ds_sit_tot_turno`` preenchido); o outro foi indeferido sem votação.
    """
    c22 = cand.filter(pl.col("ano_eleicao") == 2022)
    missao = cand.filter(
        (pl.col("ano_eleicao") == 2026) & (pl.col("nr_partido") == NR_PARTIDO_MISSAO)
    )
    pessoas = pl.concat(
        [
            missao.get_column("pessoa_id"),
            c22.filter(pl.col("sq_candidato").is_in(list(indicados))).get_column("pessoa_id"),
        ]
    ).drop_nulls()
    return (
        c22.filter(pl.col("pessoa_id").is_in(pessoas.implode()))
        .sort(
            [pl.col("ds_sit_tot_turno").is_not_null(), "sq_candidato"],
            descending=[True, False],
        )
        .unique(subset="pessoa_id", keep="first", maintain_order=True)
        .sort("sq_candidato")
    )
