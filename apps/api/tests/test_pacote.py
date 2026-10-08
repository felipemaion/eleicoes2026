"""Garante que o pacote do workspace é importável (substituir por testes reais)."""

import api


def test_pacote_importavel() -> None:
    assert api.__doc__
