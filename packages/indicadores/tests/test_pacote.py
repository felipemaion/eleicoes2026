"""Garante que o pacote do workspace é importável (substituir por testes reais)."""

import indicadores
import pytest


def test_pacote_importavel() -> None:
    assert indicadores.__doc__


def test_colunas_tse_existem_no_contrato() -> None:
    from contratos.tse import VOTACAO_CANDIDATO_MUNZONA
    from indicadores import _colunas

    assert _colunas.QT_VOTOS_NOMINAIS_VALIDOS in VOTACAO_CANDIDATO_MUNZONA.colunas
    with pytest.raises(ImportError, match="ausente do contrato"):
        _colunas._de(VOTACAO_CANDIDATO_MUNZONA, "coluna_que_nao_existe")
