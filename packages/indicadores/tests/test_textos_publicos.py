"""Integridade dos textos públicos (docs/metodologia/publico/textos.json, T-A05).

O frontend exibe estes textos sem revisão adicional; este teste garante que cada indicador da
spec tem explicação pública, que os limites de tamanho valem e que as referências cruzadas
(vetor, âncora da spec, avisos citados pelas telas, placeholders) apontam para algo existente.
"""

import csv
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
REFERENCIA_MBL = RAIZ / "data" / "reference" / "mbl_2022.csv"

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
            assert isinstance(valor, str), f"{chave}.{campo} não é texto"
            assert valor.strip(), f"{chave}.{campo} vazio"
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
            assert isinstance(valor, str), f"tela {nome}.{campo} não é texto"
            assert valor.strip(), f"tela {nome}.{campo} vazio"
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
        assert aviso["titulo"].strip(), f"aviso {chave} sem título"
        assert aviso["texto"].strip(), f"aviso {chave} sem texto"
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
    # Placeholders globais valem em todo o arquivo; os do comparador ({busca}, {n}…) são
    # preenchidos só pela tela do comparador e não podem vazar para outras seções.
    globais = set(textos["placeholders"])
    fora = {k: v for k, v in textos.items() if k != "comparador"}
    usados = {p for s in _textos_de(fora) for p in PLACEHOLDER.findall(s)}
    assert usados <= globais, f"placeholders não declarados: {sorted(usados - globais)}"
    comp = textos["comparador"]
    locais = globais | set(comp["placeholders"])
    usados_comp = {p for s in _textos_de(comp["ui"]) for p in PLACEHOLDER.findall(s)}
    assert usados_comp <= locais, f"comparador: placeholders {sorted(usados_comp - locais)}"


def _referencia_mbl() -> list[dict[str, str]]:
    with REFERENCIA_MBL.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _nome_publico(nome_urna: str) -> str:
    return nome_urna.title()


GRUPOS_EXPLICADOS = ("mbl_2022_indicados", "mbl_2022", "mbl_2026", "missao_2026")
TERMOS_DO_COMPARADOR = ("indicados", "grupo_mbl_2022", "grupo_mbl_2026", "comparador")


def test_glossario_explica_indicados_grupos_e_comparador(textos: dict[str, Any]) -> None:
    glossario = textos["glossario"]
    for chave in TERMOS_DO_COMPARADOR:
        assert chave in glossario, f"glossário sem {chave!r}"
    ref = _referencia_mbl()
    indicados = [_nome_publico(r["nome"]) for r in ref if r["origem"] == "indicado"]
    assert len(indicados) == 4
    for nome in indicados:
        assert nome in glossario["indicados"]["definicao"], f"indicados não cita {nome}"
    assert f"{len(ref)} candidaturas" in glossario["grupo_mbl_2022"]["definicao"]
    fora_do_missao = [r for r in ref if r["partido_2026"] != "MISSÃO" and r["sq_candidato_2026"]]
    for r in fora_do_missao:
        assert _nome_publico(r["nome"]) in glossario["grupo_mbl_2026"]["definicao"]
    for termo in ("cargo", "zona"):
        assert termo in glossario["comparador"]["definicao"]


def test_textos_do_comparador(textos: dict[str, Any]) -> None:
    comp = textos["comparador"]
    limites: dict[str, int] = textos["limites"]
    assert comp["ui"], "comparador sem textos de interface"
    for chave, valor in comp["ui"].items():
        assert isinstance(valor, str) and valor.strip(), f"comparador.ui.{chave} vazio"
        assert len(valor) <= limites["aviso"], f"comparador.ui.{chave} acima do limite"
    assert set(comp["nota_grupo"]) == set(GRUPOS_EXPLICADOS)
    for chave, nota in comp["nota_grupo"].items():
        assert 0 < len(nota) <= limites["definicao"], f"comparador.nota_grupo.{chave}"
    # Os nomes dos indicados vêm da referência, não de memória.
    ref = _referencia_mbl()
    for r in ref:
        if r["origem"] == "indicado":
            assert _nome_publico(r["nome"]) in comp["nota_grupo"]["mbl_2022_indicados"]
    assert "{busca}" in comp["ui"]["sem_resultado"]
    assert "{n}" in comp["ui"]["refine"] and "{total}" in comp["ui"]["refine"]


def test_sem_espacos_sobrando(textos: dict[str, Any]) -> None:
    for s in _textos_de(textos):
        assert s == s.strip(), f"espaço nas pontas em {s!r}"
        assert "  " not in s, f"espaço duplo em {s!r}"


def test_pagina_como_ler_existe_e_cobre_os_avisos() -> None:
    texto = COMO_LER.read_text(encoding="utf-8")
    assert texto.startswith("# Como ler este painel")
    termos = ("penetração", "legenda", "rezoneamento", "PTB", "parciais", "IPCA", "indicados")
    for termo in (*termos, "Beraldo", "comparador"):
        assert termo.lower() in texto.lower(), f"'Como ler' não menciona {termo}"
