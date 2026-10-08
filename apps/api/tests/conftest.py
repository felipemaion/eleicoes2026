"""Fixtures compartilhadas: app real (DuckDB sobre Parquet) com grupos de teste."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient

# Valor fixo explícito para os testes: produção exige a variável (sem default silencioso).
os.environ.setdefault("ELEICOES_VERSAO_APP", "teste")

FIXTURES = Path(__file__).parent / "fixtures"
RAIZ = Path(__file__).resolve().parents[3]
VETORES = RAIZ / "docs" / "metodologia" / "vetores"


def settings_fixture() -> Settings:
    """Settings apontando para os Parquet e grupos de teste (CSV relativo a fixtures/)."""
    return Settings(
        dir_dados=FIXTURES,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        versao_app="teste",
        aquecer=False,  # os testes ligam o aquecimento explicitamente
    )


@pytest.fixture
def api() -> Iterator[TestClient]:
    """Cliente HTTP sobre a app com a fixture de domínio."""
    with TestClient(criar_app(settings_fixture())) as cliente:
        yield cliente
