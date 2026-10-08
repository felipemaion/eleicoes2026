"""Configuração de testes do pacote indicadores."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # Registrado aqui (e não no pyproject da raiz) para ficar no território do pacote.
    config.addinivalue_line("markers", "lento: teste de desempenho com dados sintéticos grandes")
