"""T-B08: gastos completos na ficha, links oficiais do TSE e blocos de procedência.

Fixture: sq 3 (Missão, Dep. Federal SP, 2026) tem despesa própria 100000 (paga 80000), um repasse
de 400 a outros candidatos/partidos e 1000 votos; sq 11 é presidente; 2022/1 tem contas de 40000.
"""

import pytest
from api import fontes, links
from fastapi.testclient import TestClient

METODOLOGIA = "https://github.com/felipemaion/eleicoes2026/blob/main/docs/metodologia/"


def _por_dataset(corpo: dict[str, object]) -> dict[str, dict[str, object]]:
    return {f["dataset"]: f for f in corpo["fontes"]}  # type: ignore[attr-defined,index]


# ------------------------------------------------------------------ gastos na ficha
def test_ficha_traz_totais_receita_e_custo_com_e_sem_repasses(api: TestClient) -> None:
    g = api.get("/api/candidatos/2026/3").json()["gastos"]
    assert g["despesa_contratada"] == 100000.0  # própria campanha, sem repasse
    assert g["repasses_contratados"] == pytest.approx(400.0)
    assert g["repasses_pagos"] == pytest.approx(400.0)
    assert g["despesa_total_contratada"] == pytest.approx(100400.0)
    assert g["despesa_total_paga"] == pytest.approx(80400.0)
    assert g["custo_voto_contratado"] == pytest.approx(100.0)
    assert g["custo_voto_contratado_com_repasses"] == pytest.approx(100.4)
    assert g["custo_voto_pago_com_repasses"] == pytest.approx(80.4)
    assert g["receita_total"] == 100000.0
    assert g["receita_por_fonte"]["fefc"] == 50000.0
    assert "repasses" in g["explicacao_repasses"].lower()


def test_ficha_gastos_2022_deflacionados_incluem_repasses_zerados(api: TestClient) -> None:
    g = api.get("/api/candidatos/2022/1").json()["gastos"]
    fator = 1.005**48
    assert g["despesa_total_contratada"] == pytest.approx(40000 * fator)
    assert g["repasses_contratados"] == 0.0


# ------------------------------------------------------------------ links oficiais
def test_ficha_links_oficiais_2026_dep_federal(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/2026/3").json()
    por_tipo = {x["tipo"]: x for x in corpo["links"]}
    votos = por_tipo["votos_oficiais"]
    assert votos["url"] == (
        "https://resultados.tse.jus.br/oficial/app/index.html"
        "#/eleicao/6257/uf/sp/cargo/6/vis/nominal/resultados"
    )
    assert votos["verificado"] is True
    lista = por_tipo["divulgacand_lista"]
    assert lista["url"].startswith("https://divulgacandcontas.tse.jus.br/divulga/#/candidato/")
    assert lista["url"].endswith("/20322002026")
    assert por_tipo["divulgacand_candidato"]["url"].endswith("/SP/SP/20322002026/3/2026/SP")
    assert por_tipo["divulgacand_candidato"]["verificado"] is True
    assert por_tipo["dados_abertos_contas"]["url"] == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
        "prestacao_de_contas_eleitorais_candidatos_2026.zip"
    )
    assert por_tipo["dados_abertos_votos"]["url"].endswith(
        "votacao_candidato_munzona/votacao_candidato_munzona_2026.zip"
    )
    assert all(x["nota"] for x in corpo["links"] if not x["verificado"])


def test_links_presidente_usam_br_e_cd_eleicao_federal() -> None:
    sp = links.links_da_candidatura(ano=2026, sq_candidato=11, uf="BR", cargo="PRESIDENTE")
    votos = next(x for x in sp if x.tipo == "votos_oficiais")
    assert votos.url.endswith("#/eleicao/6257/uf/br/cargo/1/vis/nominal/resultados")
    cand = next(x for x in sp if x.tipo == "divulgacand_candidato")
    assert cand.url.endswith("/BR/BR/20322002026/11/2026/BR")


def test_links_governador_2026_usa_eleicao_estadual() -> None:
    ls = links.links_da_candidatura(ano=2026, sq_candidato=7, uf="MG", cargo="GOVERNADOR")
    votos = next(x for x in ls if x.tipo == "votos_oficiais")
    assert "/eleicao/6259/uf/mg/cargo/3/" in votos.url


def test_links_2022_sem_resultados_ao_vivo_e_com_nota() -> None:
    ls = links.links_da_candidatura(ano=2022, sq_candidato=1, uf="SP", cargo="DEPUTADO FEDERAL")
    assert not [x for x in ls if x.tipo == "votos_oficiais" and x.verificado]
    cand = next(x for x in ls if x.tipo == "divulgacand_candidato")
    assert "/SP/SP/2040602022/1/2022/SP" in cand.url
    assert any(x.tipo == "dados_abertos_contas" and "_2022.zip" in x.url for x in ls)


# ------------------------------------------------------------------ procedência
def test_catalogo_de_fontes_e_unico_e_aponta_para_a_spec() -> None:
    f = fontes.fonte("votacao_candidato_munzona", ano=2026, dt_geracao="2026-10-06")
    assert f.dt_geracao == "2026-10-06"
    assert f.arquivo_oficial_url.endswith("votacao_candidato_munzona_2026.zip")
    assert f.metodologia_url.startswith(METODOLOGIA)
    assert "#" in f.metodologia_url
    assert f.coluna_regra
    with pytest.raises(KeyError):
        fontes.fonte("inexistente", ano=2026, dt_geracao="x")


@pytest.mark.parametrize(
    ("caminho", "params", "datasets"),
    [
        ("/api/candidatos", {"grupo": "missao_2026"}, {"votacao_candidato_munzona"}),
        (
            "/api/candidatos/2026/3",
            {},
            {"votacao_candidato_munzona", "prestacao_contas", "consulta_cand"},
        ),
        (
            "/api/mapa",
            {"ano": 2026, "cargo": "DEPUTADO FEDERAL", "grupo": "missao_2026"},
            {"votacao_candidato_munzona", "detalhe_votacao_munzona"},
        ),
        ("/api/gastos", {"grupo": "missao_2026"}, {"prestacao_contas"}),
        (
            "/api/comparativo",
            {"comparacao": "evolucao_mbl", "cargo": "DEPUTADO FEDERAL"},
            {"votacao_candidato_munzona", "detalhe_votacao_munzona"},
        ),
    ],
)
def test_respostas_principais_trazem_fontes(
    api: TestClient, caminho: str, params: dict[str, object], datasets: set[str]
) -> None:
    r = api.get(caminho, params=params)
    assert r.status_code == 200, r.text
    corpo = r.json()
    por = _por_dataset(corpo)
    assert datasets <= set(por), por.keys()
    for f in por.values():
        assert set(f) == {
            "dataset",
            "arquivo_oficial_url",
            "dt_geracao",
            "coluna_regra",
            "metodologia_url",
        }
        assert f["arquivo_oficial_url"].startswith("http")
        assert f["metodologia_url"].startswith(METODOLOGIA)
    esperado = api.get("/api/meta").json()["dt_geracao"]
    assert {f["dt_geracao"] for f in por.values()} == {esperado}
