"""Revisão de segurança do PR #43: limites do DuckDB, semáforo, single-flight, cache da ficha."""

import threading
from pathlib import Path

import duckdb
import pytest
from api.cache_servico import CacheLRU
from api.erros import ErroDominio
from api.repositorio.duckdb import RepositorioDuckDB
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
DF = "DEPUTADO FEDERAL"


# --------------------------------------------------------------- limites do DuckDB
def test_duckdb_abre_com_limites_de_memoria_e_de_temporarios(tmp_path: Path) -> None:
    temp = tmp_path / "duck"
    repo = RepositorioDuckDB(
        FIXTURES, memory_limit="1200MB", max_temp_directory_size="400MB", temp_directory=temp
    )
    linhas = dict(
        repo._linhas(
            "SELECT name, value FROM duckdb_settings()"
            " WHERE name IN ('memory_limit', 'max_temp_directory_size', 'temp_directory')"
        )  # type: ignore[arg-type]
    )
    assert str(linhas["memory_limit"]).startswith("1.1")  # 1200 MB ≈ 1,1 GiB
    assert str(linhas["max_temp_directory_size"]).startswith("381")  # 400 MB ≈ 381,4 MiB
    assert linhas["temp_directory"] == str(temp)


def test_limites_ficam_travados_depois_da_abertura(tmp_path: Path) -> None:
    repo = RepositorioDuckDB(FIXTURES, temp_directory=tmp_path / "duck")
    with pytest.raises(duckdb.Error, match=r"locked|Cannot"):
        repo._linhas("SET memory_limit = '64GB'")


# --------------------------------------------------------------- semáforo
def test_semaforo_devolve_503_quando_excede_os_calculos_simultaneos() -> None:
    cache = CacheLRU(simultaneos=1, espera_s=0.05)
    dentro, soltar = threading.Event(), threading.Event()

    def lento() -> int:
        dentro.set()
        soltar.wait(5)
        return 1

    t = threading.Thread(target=lambda: cache.obter("d", "a", lento))
    t.start()
    assert dentro.wait(5)
    with pytest.raises(ErroDominio) as erro:
        cache.obter("d", "b", lambda: 2)
    assert erro.value.status == 503
    assert erro.value.codigo == "servidor_ocupado"
    soltar.set()
    t.join(5)
    assert cache.obter("d", "b", lambda: 2) == 2  # vaga liberada


def test_hit_de_cache_nao_consome_vaga_do_semaforo() -> None:
    cache = CacheLRU(simultaneos=1)
    cache.obter("d", "a", lambda: 1)
    dentro, soltar = threading.Event(), threading.Event()

    def lento() -> int:
        dentro.set()
        soltar.wait(5)
        return 2

    t = threading.Thread(target=lambda: cache.obter("d", "b", lento))
    t.start()
    assert dentro.wait(5)
    assert cache.obter("d", "a", lambda: 99) == 1  # hit passa mesmo com a vaga ocupada
    soltar.set()
    t.join(5)


# --------------------------------------------------------------- single-flight
def test_single_flight_calcula_uma_vez_para_chamadas_simultaneas() -> None:
    cache = CacheLRU(simultaneos=1)  # 1 vaga: só o líder pode calcular, os demais esperam
    chamadas = []
    liberar = threading.Event()

    def calcular() -> int:
        chamadas.append(1)
        liberar.wait(5)
        return 7

    resultados: list[int] = []
    ts = [
        threading.Thread(target=lambda: resultados.append(cache.obter("d", "k", calcular)))
        for _ in range(6)
    ]
    for t in ts:
        t.start()
    while not chamadas:
        pass
    liberar.set()
    for t in ts:
        t.join(5)
    assert len(chamadas) == 1
    assert resultados == [7] * 6


def test_falha_do_lider_nao_envenena_a_chave() -> None:
    cache = CacheLRU()

    def quebra() -> int:
        raise RuntimeError("falhou")

    with pytest.raises(RuntimeError):
        cache.obter("d", "k", quebra)
    assert cache.obter("d", "k", lambda: 5) == 5


# --------------------------------------------------------------- rotas
def test_ficha_do_candidato_entra_no_cache(api: TestClient) -> None:
    antes = len(api.app.state.cache)  # type: ignore[attr-defined]
    assert api.get("/api/candidatos/2026/3").status_code == 200
    assert len(api.app.state.cache) == antes + 1  # type: ignore[attr-defined]


@pytest.mark.parametrize("nivel", ["zona", "h3"])
def test_nivel_fino_exige_uf(api: TestClient, nivel: str) -> None:
    r = api.get(
        "/api/mapa", params={"ano": 2026, "cargo": DF, "grupo": "missao_2026", "nivel": nivel}
    )
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "uf_obrigatoria"


def test_503_de_servidor_ocupado_traz_retry_after(api: TestClient) -> None:
    cache = api.app.state.cache  # type: ignore[attr-defined]
    cache._vagas.acquire()  # ocupa a única vaga... e as demais
    try:
        while cache._vagas.acquire(blocking=False):
            pass
        r = api.get(
            "/api/mapa", params={"ano": 2026, "cargo": DF, "uf": "RJ", "grupo": "missao_2026"}
        )
    finally:
        pass
    assert r.status_code == 503
    assert r.headers["retry-after"]
    assert r.json()["detail"]["codigo"] == "servidor_ocupado"
