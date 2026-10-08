"""T-B07: varredura de todos os endpoints × cargos × grupos × UF sobre a fixture — sem 5xx."""

import importlib.util
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

SCRIPT = Path(__file__).parents[1] / "scripts" / "varredura.py"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("varredura", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def varredura() -> ModuleType:
    """O script carregado como módulo (scripts/ não é pacote)."""
    return _carregar()


def _get(api: TestClient) -> Any:
    def get(caminho: str, params: dict[str, object]) -> tuple[int, Any, float]:
        ini = time.perf_counter()
        r = api.get(caminho, params=params)  # type: ignore[arg-type]
        try:
            corpo = r.json()
        except ValueError:
            corpo = None  # 500 do servidor vem como texto
        return r.status_code, corpo, time.perf_counter() - ini

    return get


def test_nenhum_endpoint_responde_5xx(api: TestClient, varredura: ModuleType) -> None:
    rel = varredura.executar(_get(api), ufs=("SP", "RJ", "AC"))
    assert rel.total > 500, "a varredura precisa cobrir muitas combinações"
    assert rel.ok, f"5xx: {rel.cinco_xx[:5]} sem JSON: {rel.nao_json[:5]}"
    assert rel.por_status.get(200, 0) > 100  # não vale se tudo for 422
    assert set(rel.por_status) <= {200, 404, 422}


def test_varredura_inclui_presidente_e_candidatos_majoritarios(
    api: TestClient, varredura: ModuleType
) -> None:
    pedidos = list(varredura.pedidos(_get(api), ("SP",)))
    assert ("/api/candidatos/2026/11", {}) in pedidos  # ficha do presidente
    assert any(
        c == "/api/mapa" and p.get("cargo") == "PRESIDENTE" and p.get("sq_candidato") == 11
        for c, p in pedidos
    )
    assert any(c == "/api/mapa/pontos" and p.get("uf") is None for c, p in pedidos)
    assert any(c == "/api/comparativo" and "pessoas" in p for c, p in pedidos)
