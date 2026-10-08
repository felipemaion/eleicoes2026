"""Critério 3 da T-A02: indicadores municipais de um cargo×UF do porte de SP em < 2 s."""

import random
import time

import polars as pl
import pytest
from indicadores import desempenho, espacial

N_MUNICIPIOS = 645
N_CANDIDATOS = 1_500


@pytest.mark.lento
def test_cargo_uf_grande_em_menos_de_dois_segundos() -> None:
    rng = random.Random(20261004)  # noqa: S311 - dados sintéticos reprodutíveis
    aptos = [rng.randint(1_000, 500_000) for _ in range(N_MUNICIPIOS)]
    municipios = pl.DataFrame(
        {
            "cd_mun_ibge": list(range(3_500_000, 3_500_000 + N_MUNICIPIOS)),
            "aptos": aptos,
            "validos": [a * 7 // 10 for a in aptos],
        }
    )
    # Como no TSE, o candidato só tem linha onde recebeu voto (~1/3 dos municípios).
    linhas = [
        (f"c{c}", 3_500_000 + m, rng.randint(1, 30))
        for c in range(N_CANDIDATOS)
        for m in range(N_MUNICIPIOS)
        if rng.random() < 0.33
    ]
    votos = pl.DataFrame(linhas, schema=["sq_candidato", "cd_mun_ibge", "votos"], orient="row")

    inicio = time.perf_counter()
    tabela = desempenho.indicadores_municipais(votos, municipios)
    conc = espacial.concentracao(tabela)
    uf = desempenho.totais_uf(tabela)
    decorrido = time.perf_counter() - inicio

    assert tabela.height == N_MUNICIPIOS * N_CANDIDATOS
    assert conc.height == uf.height == N_CANDIDATOS
    assert decorrido < 2.0, f"{decorrido:.2f} s"
