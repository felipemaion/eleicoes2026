"""Integração de /api/health e /api/meta com DuckDB real sobre a fixture Parquet."""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures"


def _settings(dir_dados: Path, **extra: object) -> Settings:
    return Settings(dir_dados=dir_dados, arquivo_grupos=RAIZ / "config" / "grupos.yaml", **extra)  # type: ignore[arg-type]


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    with TestClient(criar_app(_settings(FIXTURES))) as c:
        yield c


def test_health_ok(cliente: TestClient) -> None:
    r = cliente.get("/api/health")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "ok"
    assert corpo["versao"]
    assert corpo["dt_geracao"] == "2026-10-06T12:00:00"


def test_health_503_quando_dados_nao_abrem(tmp_path: Path) -> None:
    with TestClient(criar_app(_settings(tmp_path / "inexistente"))) as c:
        r = c.get("/api/health")
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "dados_indisponiveis"


def test_meta_lista_anos_ufs_cargos_e_grupos(cliente: TestClient) -> None:
    corpo = cliente.get("/api/meta").json()
    assert corpo["anos"] == [2022, 2026]
    assert corpo["ufs"] == ["RJ", "SP"]
    assert corpo["cargos"] == ["DEPUTADO ESTADUAL", "DEPUTADO FEDERAL"]
    ids = {g["id"] for g in corpo["grupos"]}
    assert {"missao_2026", "mbl_2022"} <= ids
    assert corpo["dt_geracao"] == "2026-10-06T12:00:00"


def test_meta_503_quando_dados_nao_abrem(tmp_path: Path) -> None:
    with TestClient(criar_app(_settings(tmp_path / "x"))) as c:
        assert c.get("/api/meta").status_code == 503


def test_threads_configuravel_e_configuracao_travada() -> None:
    from api.repositorio.duckdb import RepositorioDuckDB

    repo = RepositorioDuckDB(FIXTURES, threads=2)
    try:
        assert repo.threads() == 2
        with pytest.raises(duckdb.Error):
            repo._con.execute("SET threads = 8")
    finally:
        repo.fechar()


def test_cors_restrito_por_config() -> None:
    app = criar_app(_settings(FIXTURES, cors_origens=["https://ok.example"]))
    with TestClient(app) as c:
        ok = c.get("/api/health", headers={"Origin": "https://ok.example"})
        ruim = c.get("/api/health", headers={"Origin": "https://mau.example"})
    assert ok.headers["access-control-allow-origin"] == "https://ok.example"
    assert "access-control-allow-origin" not in ruim.headers


def test_meta_concorrente_em_varias_threads(cliente: TestClient) -> None:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        respostas = list(pool.map(lambda _: cliente.get("/api/meta"), range(40)))
    assert {r.status_code for r in respostas} == {200}
    assert all(r.json()["anos"] == [2022, 2026] for r in respostas)


def test_503_nao_vaza_detalhes_internos(tmp_path: Path) -> None:
    with TestClient(criar_app(_settings(tmp_path / "segredo"))) as c:
        r = c.get("/api/health")
    assert r.json() == {"detail": {"codigo": "dados_indisponiveis"}}
    assert "segredo" not in r.text


def test_health_503_quando_dados_param_de_responder() -> None:
    app = criar_app(_settings(FIXTURES))
    with TestClient(app) as c:
        app.state.repositorio._con.close()
        r = c.get("/api/health")
        app.state.repositorio = None
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "dados_indisponiveis"


def test_caminhos_padrao_sao_absolutos() -> None:
    cfg = Settings()
    assert cfg.dir_dados.is_absolute()
    assert cfg.arquivo_grupos.is_absolute()
    assert cfg.arquivo_grupos.name == "grupos.yaml"
