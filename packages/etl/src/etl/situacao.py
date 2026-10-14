"""Situação da candidatura: o campo derivado ``foi_as_urnas`` (T-D11).

O ``consulta_cand`` de 2026 publica ``DS_SITUACAO_CANDIDATURA`` como ``#NE`` e não traz
``DS_DETALHE_SITUACAO_CAND``; logo a situação cadastral não separa o registro substituído
do que concorreu. O que o TSE preenche de forma consistente nos dois anos é o resultado do
turno (``CD_SIT_TOT_TURNO``): só candidatura que constou na urna recebe resultado.
"""

from __future__ import annotations

import polars as pl


def foi_as_urnas() -> pl.Expr:
    """Candidatura que constou na urna (apta, ou sub judice) = tem resultado no turno.

    Fonte única da regra: registros substituídos, cancelados ou indeferidos sem urna ficam
    sem ``cd_sit_tot_turno`` (nulo após o tratamento de ``-1``/``#NULO``).
    """
    return pl.col("cd_sit_tot_turno").is_not_null().alias("foi_as_urnas")
