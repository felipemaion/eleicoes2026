"""Leitura de config/grupos.yaml."""

from pathlib import Path

import pytest
from api.servicos.meta import carregar_grupos

RAIZ = Path(__file__).resolve().parents[3]


def test_carrega_grupos_reais() -> None:
    grupos = {g.id: g for g in carregar_grupos(RAIZ / "config" / "grupos.yaml")}
    assert grupos["mbl_2022"].ano == 2022
    assert grupos["missao_2026"].rotulo.startswith("Partido Missão")


def test_arquivo_ausente_falha_alto(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        carregar_grupos(tmp_path / "nao_existe.yaml")
