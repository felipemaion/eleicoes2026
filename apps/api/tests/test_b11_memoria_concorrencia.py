"""T-B11: memória do DuckDB, OOM como 503 e fila curta por vaga (prioridade a usuários)."""

import logging
import threading
import time
from pathlib import Path

import duckdb
import pytest
from api.cache_servico import CacheLRU
from api.config import Settings
from api.erros import ErroDominio
from api.main import criar_app
from api.repositorio.base import MemoriaInsuficiente
from api.repositorio.duckdb import RepositorioDuckDB
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def _config(con: duckdb.DuckDBPyConnection, nome: str) -> str:
    linha = con.execute(f"SELECT current_setting('{nome}')").fetchone()
    assert linha is not None
    return str(linha[0])


# ----------------------------------------------------------- 1. limites efetivos
def test_limites_efetivos_sao_os_configurados() -> None:
    repo = RepositorioDuckDB(
        FIXTURES, threads=2, memory_limit="1200MB", max_temp_directory_size="400MB"
    )
    try:
        ref = duckdb.connect(":memory:")
        ref.execute("SET memory_limit = '1200MB'")
        ref.execute("SET max_temp_directory_size = '400MB'")
        efetivo = repo.configuracao()
        assert efetivo["memory_limit"] == _config(ref, "memory_limit")
        assert efetivo["max_temp_directory_size"] == _config(ref, "max_temp_directory_size")
        assert efetivo["threads"] == "2"
        assert efetivo["temp_directory"]
    finally:
        repo.fechar()


def test_settings_padrao_pede_1200mb_de_memoria() -> None:
    assert Settings().duck_memory_limit == "1200MB"


def test_startup_loga_a_configuracao_efetiva(caplog: pytest.LogCaptureFixture) -> None:
    cfg = Settings(dir_dados=FIXTURES, aquecer=False)
    with caplog.at_level(logging.INFO), TestClient(criar_app(cfg)):
        pass
    msg = " ".join(r.getMessage() for r in caplog.records)
    for chave in ("memory_limit", "temp_directory", "threads", "max_temp_directory_size"):
        assert chave in msg


# ------------------------------------------------- 2. filtro desce ao scan (sem semi-join)
def test_consulta_por_candidato_nao_usa_semi_join() -> None:
    repo = RepositorioDuckDB(FIXTURES)
    try:
        sql = (
            "EXPLAIN SELECT cd_mun_ibge FROM votos_munzona WHERE ano = 2026 AND sq_candidato IN (3)"
        )
        plano = str(repo._con.execute(sql).fetchall())
        assert "SEMI" not in plano.upper()
        assert repo.votos_territorio(2026, [], por_zona=False) == []  # lista vazia não quebra
    finally:
        repo.fechar()


# ------------------------------------------------------------ 3. OOM nunca vira 500
def test_oom_do_duckdb_vira_memoria_insuficiente() -> None:
    repo = RepositorioDuckDB(FIXTURES, memory_limit="30MB", max_temp_directory_size="0KB")
    try:
        with pytest.raises(MemoriaInsuficiente):
            repo._linhas("SELECT count(*), list(i) FROM range(30000000) t(i)")
    finally:
        repo.fechar()


def test_handler_de_oom_responde_503_com_retry_after() -> None:
    from api.main import responder_memoria_insuficiente

    resp = responder_memoria_insuficiente(MemoriaInsuficiente("x"))
    assert resp.status_code == 503
    assert resp.headers["retry-after"]
    assert b"memoria_insuficiente" in resp.body


# ------------------------------------------------------ 4. fila curta e prioridade
def test_espera_curta_por_vaga_em_vez_de_recusar_na_hora() -> None:
    cache = CacheLRU(simultaneos=1, espera_s=3)
    dentro = threading.Event()

    def lento() -> int:
        dentro.set()
        time.sleep(0.3)
        return 1

    t = threading.Thread(target=lambda: cache.obter("d", "a", lento))
    t.start()
    assert dentro.wait(5)
    assert cache.obter("d", "b", lambda: 2) == 2  # esperou ~0,3 s pela vaga, sem 503
    t.join(5)


def test_estoura_a_espera_vira_503() -> None:
    cache = CacheLRU(simultaneos=1, espera_s=0.1)
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
    soltar.set()
    t.join(5)


def test_aquecimento_nao_toma_vaga_se_ha_fila_de_usuarios() -> None:
    cache = CacheLRU(simultaneos=2, espera_s=3)
    dentro, soltar = threading.Event(), threading.Event()
    ocupados = []

    def lento(n: int) -> int:
        ocupados.append(n)
        if len(ocupados) == 2:
            dentro.set()
        soltar.wait(5)
        return n

    ts = [
        threading.Thread(target=lambda n=n: cache.obter("d", n, lambda: lento(n))) for n in (1, 2)
    ]
    for t in ts:
        t.start()
    assert dentro.wait(5)  # as 2 vagas estão ocupadas
    usuario = threading.Thread(target=lambda: cache.obter("d", 3, lambda: 3))
    usuario.start()
    while cache.na_fila == 0:
        time.sleep(0.01)
    with pytest.raises(ErroDominio) as erro, cache.baixa_prioridade():
        cache.obter("d", 4, lambda: 4)
    assert erro.value.status == 503  # cedeu: há usuário na fila
    soltar.set()
    for t in (*ts, usuario):
        t.join(5)


def test_aquecimento_usa_no_maximo_uma_vaga() -> None:
    cache = CacheLRU(simultaneos=3, espera_s=1)
    dentro, soltar = threading.Event(), threading.Event()

    def lento() -> int:
        dentro.set()
        soltar.wait(5)
        return 1

    def aquecer() -> None:
        with cache.baixa_prioridade():
            cache.obter("d", "w1", lento)

    t = threading.Thread(target=aquecer)
    t.start()
    assert dentro.wait(5)
    with pytest.raises(ErroDominio), cache.baixa_prioridade():
        cache.obter("d", "w2", lambda: 2)  # segunda vaga de baixa prioridade é recusada
    assert cache.obter("d", "u", lambda: 3) == 3  # usuário ainda tem vaga
    soltar.set()
    t.join(5)


# ------------------------------------------------ achado na varredura com dados reais
@pytest.mark.parametrize("cargo", ["VICE-GOVERNADOR", "VICE-PRESIDENTE", "1º SUPLENTE"])
def test_links_de_cargo_fora_do_enum_nao_quebram(cargo: str) -> None:
    from api.links import links_da_candidatura

    assert links_da_candidatura(ano=2022, sq_candidato=1, uf="RJ", cargo=cargo)  # 2022 não quebra
    links = links_da_candidatura(ano=2026, sq_candidato=1, uf="RJ", cargo=cargo)
    tipos = [lk.tipo for lk in links]
    assert "votos_oficiais" not in tipos  # a página por cargo só existe para titulares
    assert "divulgacand_ficha_json" in tipos
