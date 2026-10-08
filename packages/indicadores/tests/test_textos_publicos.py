"""Integridade dos textos públicos (docs/metodologia/publico/textos.json, T-A05).

O frontend exibe estes textos sem revisão adicional; este teste garante que cada indicador da
spec tem explicação pública, que os limites de tamanho valem e que as referências cruzadas
(vetor, âncora da spec, avisos citados pelas telas, placeholders) apontam para algo existente.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[3]
METODOLOGIA = RAIZ / "docs" / "metodologia"
TEXTOS = METODOLOGIA / "publico" / "textos.json"
COMO_LER = METODOLOGIA / "publico" / "README.md"
SPEC = METODOLOGIA / "indicadores.md"
VETORES = sorted((METODOLOGIA / "vetores").glob("*.json"))

CAMPOS_INDICADOR = ("titulo", "resumo", "como_ler", "unidade", "denominador", "cuidado", "fonte")
TELAS = ("visao_geral", "mapa", "gastos", "evolucao", "candidato")
CAMPOS_TELA = ("titulo", "subtitulo", "nota_rodape")
AVISOS_OBRIGATORIOS = (
    "contas_parciais",
    "legenda_nao_atribuida",
    "rezoneamento",
    "grupo_mbl_2022",
    "numero_14_em_2022",
)
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _carregar() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(TEXTOS.read_text(encoding="utf-8"))
    return dados


def _textos_de(no: Any) -> list[str]:
    """Todas as strings de uma árvore JSON (para checagens transversais)."""
    if isinstance(no, str):
        return [no]
    if isinstance(no, dict):
        return [s for v in no.values() for s in _textos_de(v)]
    if isinstance(no, list):
        return [s for v in no for s in _textos_de(v)]
    return []


@pytest.fixture(scope="module")
def textos() -> dict[str, Any]:
    return _carregar()


def test_toda_chave_de_indicador_da_spec_tem_texto(textos: dict[str, Any]) -> None:
    # A spec identifica cada indicador pelo nome do seu vetor de teste.
    chaves_spec = {json.loads(v.read_text(encoding="utf-8"))["indicador"] for v in VETORES}
    assert chaves_spec, "nenhum vetor na spec"
    faltando = chaves_spec - set(textos["indicadores"])
    assert not faltando, f"indicadores da spec sem texto público: {sorted(faltando)}"


def test_campos_e_limites_dos_indicadores(textos: dict[str, Any]) -> None:
    limites: dict[str, int] = textos["limites"]
    assert limites["resumo"] == 160
    assert limites["como_ler"] == 400
    for chave, ind in textos["indicadores"].items():
        for campo in CAMPOS_INDICADOR:
            valor = ind.get(campo)
            assert isinstance(valor, str) and valor.strip(), f"{chave}.{campo} vazio"
            if campo in limites:
                assert len(valor) <= limites[campo], (
                    f"{chave}.{campo} tem {len(valor)} caracteres (máx. {limites[campo]})"
                )


def test_indicador_aponta_para_vetor_e_secao_existentes(textos: dict[str, Any]) -> None:
    vetores = {v.stem for v in VETORES}
    ancoras = set(re.findall(r'<a id="([^"]+)"></a>', SPEC.read_text(encoding="utf-8")))
    for chave, ind in textos["indicadores"].items():
        assert ind["vetor"] in vetores, f"{chave}: vetor {ind['vetor']!r} inexistente"
        assert ind["spec"] in ancoras, f"{chave}: âncora {ind['spec']!r} não está na spec"


def test_telas_completas_e_com_limites(textos: dict[str, Any]) -> None:
    limites: dict[str, int] = textos["limites"]
    assert set(textos["telas"]) == set(TELAS)
    for nome, tela in textos["telas"].items():
        for campo in CAMPOS_TELA:
            valor = tela.get(campo)
            assert isinstance(valor, str) and valor.strip(), f"tela {nome}.{campo} vazio"
            assert len(valor) <= limites[campo], f"tela {nome}.{campo} acima do limite"
        for aviso in tela["avisos"]:
            assert aviso in textos["avisos"], f"tela {nome} cita aviso inexistente {aviso!r}"
        for ind in tela["indicadores"]:
            assert ind in textos["indicadores"], f"tela {nome} cita indicador inexistente {ind!r}"


def test_avisos_padronizados(textos: dict[str, Any]) -> None:
    limites: dict[str, int] = textos["limites"]
    for obrigatorio in AVISOS_OBRIGATORIOS:
        assert obrigatorio in textos["avisos"], f"aviso obrigatório ausente: {obrigatorio}"
    for chave, aviso in textos["avisos"].items():
        assert aviso["titulo"].strip() and aviso["texto"].strip(), f"aviso {chave} vazio"
        assert len(aviso["titulo"]) <= limites["titulo"]
        assert len(aviso["texto"]) <= limites["aviso"], f"aviso {chave} acima do limite"
        assert aviso["nivel"] in {"info", "atencao"}


def test_todo_aviso_e_usado_por_alguma_tela(textos: dict[str, Any]) -> None:
    usados = {a for tela in textos["telas"].values() for a in tela["avisos"]}
    assert set(textos["avisos"]) <= usados, "aviso definido mas nenhuma tela o exibe"


def test_glossario(textos: dict[str, Any]) -> None:
    limites: dict[str, int] = textos["limites"]
    assert len(textos["glossario"]) >= 10
    for chave, termo in textos["glossario"].items():
        assert termo["termo"].strip(), f"glossário {chave} sem termo"
        assert 0 < len(termo["definicao"]) <= limites["definicao"], f"glossário {chave}"


def test_placeholders_declarados(textos: dict[str, Any]) -> None:
    declarados = set(textos["placeholders"])
    usados = {p for s in _textos_de(textos) for p in PLACEHOLDER.findall(s)}
    assert usados <= declarados, f"placeholders não declarados: {sorted(usados - declarados)}"


def test_sem_espacos_sobrando(textos: dict[str, Any]) -> None:
    for s in _textos_de(textos):
        assert s == s.strip() and "  " not in s, f"espaço sobrando em {s!r}"


def test_pagina_como_ler_existe_e_cobre_os_avisos() -> None:
    texto = COMO_LER.read_text(encoding="utf-8")
    assert texto.startswith("# Como ler este painel")
    for termo in ("penetração", "legenda", "rezoneamento", "PTB", "parciais", "IPCA"):
        assert termo.lower() in texto.lower(), f"'Como ler' não menciona {termo}"
