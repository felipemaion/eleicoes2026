"""Critério da lista MBL 2022 reproduzido via ``pessoa_id`` (T-D06)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from etl.lista_mbl import candidaturas_mbl_2022

RAIZ = Path(__file__).resolve().parents[3]
REFERENCIA = RAIZ / "data" / "reference" / "mbl_2022.csv"
PROCESSED = RAIZ / "data" / "processed" / "consulta_cand"


def _linha(ano: int, sq: int, pessoa: str, partido: int = 99, total: str | None = "ELEITO") -> dict:
    return {
        "ano_eleicao": ano, "sq_candidato": sq, "pessoa_id": pessoa,
        "nr_partido": partido, "ds_sit_tot_turno": total,
    }  # fmt: skip


def test_missao_2026_que_disputou_2022_e_indicados_sem_duplicar() -> None:
    cand = pl.DataFrame([
        _linha(2022, 1, "a"),                       # Missão 2026 depois
        _linha(2026, 10, "a", partido=14),
        _linha(2022, 2, "b"),                       # indicado (sq 2), outro partido em 2026
        _linha(2026, 11, "b", partido=11),
        _linha(2022, 3, "c"),                       # nem Missão nem indicado
        _linha(2026, 12, "c", partido=11),
        _linha(2022, 4, "d", total=None),           # 2 registros: o sem resultado cai
        _linha(2022, 5, "d", total="NÃO ELEITO"),
        _linha(2026, 13, "d", partido=14),
        _linha(2026, 14, "e", partido=14),          # Missão sem 2022
    ])  # fmt: skip
    r = candidaturas_mbl_2022(cand, indicados=[2])
    assert sorted(r["sq_candidato"].to_list()) == [1, 2, 5]
    assert r["pessoa_id"].n_unique() == 3


def test_pessoa_sem_pessoa_id_nao_entra() -> None:
    cand = pl.DataFrame([_linha(2022, 1, None), _linha(2026, 10, None, partido=14)])  # type: ignore[arg-type]
    assert candidaturas_mbl_2022(cand, indicados=[]).is_empty()


@pytest.mark.skipif(not PROCESSED.exists(), reason="consulta_cand processado não disponível")
def test_regressao_reproduz_as_18_candidaturas_de_referencia() -> None:
    ref = pl.read_csv(REFERENCIA, schema_overrides={"sq_candidato": pl.Int64})
    indicados = ref.filter(pl.col("origem") == "indicado")["sq_candidato"].to_list()
    cand = pl.read_parquet(sorted(PROCESSED.rglob("*.parquet")))
    derivada = candidaturas_mbl_2022(cand, indicados=indicados)
    assert sorted(derivada["sq_candidato"].to_list()) == sorted(ref["sq_candidato"].to_list())
    assert len(ref) == 18
