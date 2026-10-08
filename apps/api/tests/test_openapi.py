"""O OpenAPI versionado precisa refletir o código (o CI também confere o diff)."""

import json
from pathlib import Path

from api.main import criar_app

RAIZ = Path(__file__).resolve().parents[3]


def test_openapi_versionado_esta_atualizado() -> None:
    versionado = json.loads((RAIZ / "docs" / "api" / "openapi.json").read_text())
    assert versionado == json.loads(json.dumps(criar_app().openapi()))
    assert {"/api/health", "/api/meta"} <= set(versionado["paths"])
