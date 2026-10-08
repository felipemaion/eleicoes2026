"""Garante que o pacote do workspace é importável (substituir por testes reais)."""

import contratos


def test_pacote_importavel() -> None:
    assert contratos.__doc__
