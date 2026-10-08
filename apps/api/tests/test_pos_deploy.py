"""T-B04: KPIs por grupo, `indicado`, nome do município no mapa, aquecimento e User-Agent do smoke."""

import importlib.util
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient


DF = "DEPUTADO FEDERAL"
FIXTURES = Path(__file__).parent / "fixtures"


def settings_fixture(**extra: object) -> Settings:
    """Mesmas fixtures do `conftest`, com ajustes (aquecimento ligado, orçamento…)."""
    return Settings(
        dir_dados=FIXTURES,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        **extra,  # type: ignore[arg-type]
    )


# ------------------------------------------------------------ KPIs do grupo
def test_candidatos_traz_kpis_agregados_do_grupo(api: TestClient) -> None:
    corpo = api.get(
        "/api/candidatos", params={"grupo": "missao_2026", "uf": "SP", "cargo": DF}
    ).json()
    kpis = corpo["kpis"]
    assert kpis["votos"] == 1180  # sq 3 (1000) + sq 5 (180), soma única do grupo
    assert kpis["aptos"] == 17500
    assert kpis["validos"] == 12400
    assert kpis["penetracao"] == pytest.approx(1180 * 1000 / 17500)
    assert kpis["pct_validos"] == pytest.approx(100 * 1180 / 12400)


def test_kpis_nulos_sem_cargo_pois_nao_se_somam_cargos(api: TestClient) -> None:
    corpo = api.get("/api/candidatos", params={"grupo": "missao_2026"}).json()
    assert corpo["kpis"] is None


def test_kpis_nulos_quando_grupo_sem_candidatura_no_recorte(api: TestClient) -> None:
    corpo = api.get(
        "/api/candidatos", params={"grupo": "missao_2026", "uf": "SP", "cargo": "SENADOR"}
    ).json()
    assert corpo["total"] == 0
    assert corpo["kpis"] is None


# ---------------------------------------------------------------- indicado
def test_indicado_vem_da_origem_da_lista(api: TestClient) -> None:
    m26 = {
        c["sq_candidato"]: c["indicado"]
        for c in api.get("/api/candidatos", params={"grupo": "mbl_2026"}).json()["itens"]
    }
    assert m26[3] is True  # origem=indicado na linha da lista (coluna 2026)
    assert m26[4] is False  # origem=proprio
    assert m26[5] is False  # do partido, fora da lista
    m22 = {
        c["sq_candidato"]: c["indicado"]
        for c in api.get("/api/candidatos", params={"grupo": "mbl_2022"}).json()["itens"]
    }
    assert m22[1] is True and m22[2] is False


def test_ficha_tambem_traz_indicado(api: TestClient) -> None:
    assert api.get("/api/candidatos/2026/3").json()["candidato"]["indicado"] is True


# ------------------------------------------------------ nome no mapa
def test_mapa_detalhes_tem_nome_do_municipio(api: TestClient) -> None:
    corpo = api.get(
        "/api/mapa", params={"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026"}
    ).json()
    assert corpo["detalhes"]["3550308"]["nome"] == "São Paulo"
    assert all(d["nome"] for d in corpo["detalhes"].values())


def test_mapa_por_zona_usa_nome_do_municipio(api: TestClient) -> None:
    corpo = api.get(
        "/api/mapa",
        params={"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026", "nivel": "zona"},
    ).json()
    chave = next(k for k in corpo["detalhes"] if k.startswith("3550308-"))
    assert corpo["detalhes"][chave]["nome"] == "São Paulo"


# --------------------------------------------------------- aquecimento
@pytest.fixture
def api_aquecida() -> Iterator[TestClient]:
    cfg = settings_fixture(aquecer=True)
    with TestClient(criar_app(cfg)) as cliente:
        yield cliente


def test_aquecimento_preenche_o_cache_sem_bloquear_o_health(api_aquecida: TestClient) -> None:
    assert api_aquecida.get("/api/health").status_code == 200
    api_aquecida.app.state.aquecimento.join(timeout=30)  # type: ignore[attr-defined]
    estado = api_aquecida.app.state.aquecimento  # type: ignore[attr-defined]
    assert not estado.is_alive()
    assert estado.erros == 0
    assert estado.aquecidas > 0
    antes = len(api_aquecida.app.state.cache)  # type: ignore[attr-defined]
    # Pedido que o aquecimento cobre: não cria entrada nova no cache.
    api_aquecida.get("/api/candidatos", params={"grupo": "missao_2026", "uf": "SP", "cargo": DF})
    api_aquecida.get("/api/gastos", params={"grupo": "missao_2026", "uf": "SP", "cargo": DF})
    api_aquecida.get("/api/comparativo", params={"comparacao": "evolucao_mbl", "cargo": DF})
    assert len(api_aquecida.app.state.cache) == antes  # type: ignore[attr-defined]


def test_aquecimento_respeita_o_orcamento_de_entradas() -> None:
    cfg = settings_fixture(aquecer=True, aquecimento_max_entradas=2)
    with TestClient(criar_app(cfg)) as cliente:
        cliente.app.state.aquecimento.join(timeout=30)  # type: ignore[attr-defined]
        assert len(cliente.app.state.cache) <= 2  # type: ignore[attr-defined]


def test_desligado_nao_cria_aquecimento(api: TestClient) -> None:
    assert api.app.state.aquecimento is None  # type: ignore[attr-defined]


# ------------------------------------------------------- smoke: User-Agent
def test_smoke_envia_user_agent_explicito() -> None:
    vistos: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - API do http.server
            vistos.append(self.headers.get("User-Agent", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_: object) -> None:
            return

    servidor = HTTPServer(("127.0.0.1", 0), Handler)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        caminho = Path(__file__).resolve().parents[1] / "scripts" / "smoke.py"
        spec = importlib.util.spec_from_file_location("smoke_script", caminho)
        assert spec and spec.loader
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)
        smoke._get(f"http://127.0.0.1:{servidor.server_port}", "/api/health")
    finally:
        servidor.shutdown()
    assert vistos == ["eleicoes2026-smoke/1.0"]
