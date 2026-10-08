"""Integridade dos vetores de teste da spec (docs/metodologia/vetores/*.json).

Os vetores são a fonte de verdade numérica compartilhada por analise, backend e frontend;
este teste garante que cada um é bem-formado e aponta para uma seção existente da spec.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[3]
VETORES = RAIZ / "docs" / "metodologia" / "vetores"
SPEC = RAIZ / "docs" / "metodologia" / "indicadores.md"
ARQUIVOS = sorted(VETORES.glob("*.json"))


def _carregar(caminho: Path) -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
    return dados


def test_existem_vetores() -> None:
    assert ARQUIVOS, "nenhum vetor em docs/metodologia/vetores"


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda p: p.stem)
def test_vetor_bem_formado(caminho: Path) -> None:
    vetor = _carregar(caminho)
    assert vetor["indicador"] == caminho.stem
    assert vetor["versao"] >= 1
    assert vetor["tolerancia_absoluta"] > 0
    assert vetor["casos"], "vetor sem casos"
    nomes = [c["nome"] for c in vetor["casos"]]
    assert len(nomes) == len(set(nomes)), "nomes de caso repetidos"
    for caso in vetor["casos"]:
        assert "entrada" in caso
        # Cada caso define a saída esperada ou o erro esperado — nunca os dois.
        assert ("saida" in caso) != ("erro" in caso), caso["nome"]


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda p: p.stem)
def test_vetor_aponta_para_secao_da_spec(caminho: Path) -> None:
    vetor = _carregar(caminho)
    arquivo, _, ancora = vetor["spec"].partition("#")
    assert arquivo == "docs/metodologia/indicadores.md"
    ids = set(re.findall(r'<a id="([a-z0-9-]+)"></a>', SPEC.read_text(encoding="utf-8")))
    assert ancora in ids, f"âncora #{ancora} ausente na spec"


def test_toda_secao_de_indicador_tem_vetor() -> None:
    """Toda seção marcada como indicador na spec tem vetor (critério de aceite da T-A01)."""
    texto = SPEC.read_text(encoding="utf-8")
    exigidas = set(re.findall(r"Vetor: `vetores/([a-z0-9_]+)\.json`", texto))
    existentes = {p.stem for p in ARQUIVOS}
    assert exigidas, "spec não referencia vetores"
    assert exigidas <= existentes, f"vetores ausentes: {sorted(exigidas - existentes)}"
