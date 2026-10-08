"""Integração dos endpoints de domínio: DuckDB real sobre as fixtures Parquet (sem mock).

Números conferidos à mão (ver docstring de scripts/gerar_fixture.py). Grupo `missao_2026`
em Dep. Federal/SP 2026 = sq 3 (1000 votos) + sq 5 (180): SP 1100, Campinas 40, Santos 40.
"""

import pytest
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"
SP, CAMP, SANTOS = "3550308", "3509502", "3548500"


# ---------------------------------------------------------------- /grupos
def test_grupos_e_comparacoes(api: TestClient) -> None:
    corpo = api.get("/api/grupos").json()
    grupos = {g["id"]: g for g in corpo["grupos"]}
    assert grupos["missao_2026"] == {
        "id": "missao_2026",
        "rotulo": "Partido Missão 2026",
        "ano": 2026,
        "n_candidaturas": 3,
    }
    assert grupos["mbl_2026"]["n_candidaturas"] == 4  # partido 14 ∪ lista (sq 7)
    assert grupos["mbl_2022"]["n_candidaturas"] == 4
    assert grupos["mbl_2022_indicados"]["n_candidaturas"] == 1  # filtro origem=indicado
    assert corpo["comparacoes"] == [
        {
            "id": "evolucao_mbl",
            "rotulo": "MBL 2022 → MBL 2026",
            "de": "mbl_2022",
            "para": "mbl_2026",
        }
    ]


# ------------------------------------------------------------- /candidatos
def test_candidatos_do_grupo_com_indicadores(api: TestClient) -> None:
    corpo = api.get("/api/candidatos", params={"grupo": "missao_2026"}).json()
    assert corpo["total"] == 3
    por_sq = {c["sq_candidato"]: c for c in corpo["itens"]}
    assert [c["sq_candidato"] for c in corpo["itens"]] == [3, 4, 5]  # votos desc
    c3 = por_sq[3]
    assert c3["votos"] == 1000
    assert c3["pct_validos"] == pytest.approx(100 * 1000 / 12400)
    assert c3["penetracao"] == pytest.approx(1000 * 1000 / 17500)
    assert c3["resultado"] == "SUPLENTE"
    assert c3["partido"] == {"numero": 14, "sigla": "MISSÃO"}
    assert por_sq[4]["penetracao"] == pytest.approx(50.0)
    assert "pessoa_id" not in c3  # nada de identificador de pessoa na resposta


def test_candidatos_filtra_por_uf_e_cargo(api: TestClient) -> None:
    sp = api.get("/api/candidatos", params={"grupo": "missao_2026", "uf": "SP"}).json()
    assert [c["sq_candidato"] for c in sp["itens"]] == [3, 5]
    de = api.get(
        "/api/candidatos", params={"grupo": "missao_2026", "cargo": "DEPUTADO ESTADUAL"}
    ).json()
    assert [c["sq_candidato"] for c in de["itens"]] == [4]


def test_candidatos_paginacao(api: TestClient) -> None:
    corpo = api.get(
        "/api/candidatos", params={"grupo": "missao_2026", "limite": 1, "offset": 1}
    ).json()
    assert corpo["total"] == 3
    assert [c["sq_candidato"] for c in corpo["itens"]] == [4]


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"grupo": "inexistente"}, 422),
        ({"grupo": "missao_2026", "uf": "XX"}, 422),
        ({"grupo": "missao_2026", "cargo": "REI"}, 422),
        ({"grupo": "missao_2026", "limite": 100000}, 422),
        ({}, 422),
    ],
)
def test_candidatos_parametros_invalidos(
    api: TestClient, params: dict[str, object], status: int
) -> None:
    assert api.get("/api/candidatos", params=params).status_code == status


def test_grupo_desconhecido_tem_codigo_padronizado(api: TestClient) -> None:
    r = api.get("/api/candidatos", params={"grupo": "inexistente"})
    assert r.json()["detail"]["codigo"] == "grupo_desconhecido"


# --------------------------------------------------- /candidatos/{ano}/{sq}
def test_ficha_do_candidato(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/2026/3").json()
    assert corpo["candidato"]["nm_urna"] == "A"
    assert corpo["votos_total"] == 1000
    assert corpo["votos_por_uf"] == [{"uf": "SP", "votos": 1000}]
    topo = corpo["votos_por_municipio"][0]
    assert topo["cd_mun_ibge"] == int(SP)
    assert topo["nome"] == "São Paulo"
    assert topo["votos"] == 1000
    assert topo["penetracao"] == pytest.approx(1000 * 1000 / 15000)
    gastos = corpo["gastos"]  # vetor custo_por_voto c1 (transferência a candidatos excluída)
    assert gastos["despesa_contratada"] == 100000.0
    assert gastos["despesa_paga"] == 80000.0
    assert gastos["divida"] == 20000.0
    assert gastos["custo_voto_contratado"] == pytest.approx(100.0)
    assert gastos["custo_voto_pago"] == pytest.approx(80.0)
    receitas = corpo["receitas"]  # vetor receitas c1_todas_as_categorias
    assert receitas["receita_total"] == 100000.0
    assert receitas["pct_publico"] == pytest.approx(60.0)
    assert receitas["por_categoria"]["fefc"] == 50000.0
    assert corpo["contas_parciais"] is True
    assert corpo["dt_geracao"] == "2026-10-06"


def test_ficha_limita_top_municipios(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/2026/5", params={"top": 2}).json()
    assert [m["cd_mun_ibge"] for m in corpo["votos_por_municipio"]] == [int(SP), int(CAMP)]


def test_ficha_2022_deflaciona_valores_para_set_2026(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/2022/1").json()
    fator = 1.005**48
    assert corpo["base_ipca"] == "2026-09"
    assert corpo["gastos"]["despesa_contratada"] == pytest.approx(40000 * fator)
    assert corpo["receitas"]["receita_total"] == pytest.approx(40000 * fator)
    assert corpo["contas_parciais"] is False


@pytest.mark.parametrize(
    ("caminho", "status"),
    [
        ("/api/candidatos/2026/999", 404),
        ("/api/candidatos/1999/3", 422),
        ("/api/candidatos/2026/x", 422),
    ],
)
def test_ficha_erros(api: TestClient, caminho: str, status: int) -> None:
    assert api.get(caminho).status_code == status


# ------------------------------------------------------------------- /mapa
def _mapa(api: TestClient, **extra: object) -> dict[str, object]:
    params = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026", **extra}
    r = api.get("/api/mapa", params={k: v for k, v in params.items() if v is not None})
    assert r.status_code == 200, r.text
    corpo: dict[str, object] = r.json()
    return corpo


def test_mapa_municipio_penetracao_do_grupo(api: TestClient) -> None:
    corpo = _mapa(api)
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores[SP] == pytest.approx(1100 * 1000 / 15000)
    assert valores[CAMP] == pytest.approx(20.0)
    assert valores[SANTOS] == pytest.approx(80.0)
    assert corpo["unidade"] == "‰"
    assert corpo["denominador"] == "aptos"
    detalhes = corpo["detalhes"]
    assert isinstance(detalhes, dict)
    assert detalhes[SP] == {
        "votos": 1100,
        "aptos": 15000,
        "validos": 10500,
        "taxa": pytest.approx(1100 * 1000 / 15000),
    }
    escala = corpo["escala_sugerida"]
    assert isinstance(escala, dict)
    assert escala["tipo"] == "sequencial"
    assert escala["paleta"] == "viridis"
    assert len(escala["quebras"]) == 4
    assert escala["quebras"] == sorted(escala["quebras"])


def test_mapa_candidato_inclui_municipio_sem_voto_com_zero(api: TestClient) -> None:
    corpo = _mapa(api, grupo=None, sq_candidato=3)
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores[SP] == pytest.approx(1000 * 1000 / 15000)
    assert valores[CAMP] == 0.0  # aptos > 0 e nenhum voto → 0, não null


def test_mapa_pct_validos(api: TestClient) -> None:
    corpo = _mapa(api, indicador="pct_validos")
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores[SP] == pytest.approx(100 * 1100 / 10500)
    assert corpo["unidade"] == "%"
    assert corpo["denominador"] == "votos_validos"


def test_mapa_votos_absolutos_usa_simbolo_proporcional(api: TestClient) -> None:
    corpo = _mapa(api, indicador="votos")
    assert corpo["unidade"] == "votos"
    escala = corpo["escala_sugerida"]
    assert isinstance(escala, dict)
    assert escala["tipo"] == "simbolo_proporcional"
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores[SP] == 1100


def test_mapa_zona(api: TestClient) -> None:
    corpo = _mapa(api, nivel="zona")
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores[f"{SP}-1"] == pytest.approx(800 * 1000 / 10000)
    assert valores[f"{SP}-2"] == pytest.approx(300 * 1000 / 5000)


def test_mapa_h3(api: TestClient) -> None:
    corpo = _mapa(api, nivel="h3")
    valores = corpo["valores"]
    assert isinstance(valores, dict)
    assert valores["88a81000a1fffff"] == pytest.approx(800 * 1000 / 10000)
    assert valores["88a81000e5fffff"] == pytest.approx(60.0)
    detalhes = corpo["detalhes"]
    assert isinstance(detalhes, dict)
    assert detalhes["88a8100b13fffff"]["validos"] is None  # sem "válidos" por célula


@pytest.mark.parametrize(
    "extra",
    [
        {"grupo": None},  # nem grupo nem candidato
        {"sq_candidato": 3},  # os dois
        {"nivel": "zona", "uf": None},
        {"nivel": "h3", "uf": None},
        {"nivel": "h3", "indicador": "pct_validos"},
        {"nivel": "bairro"},
        {"indicador": "lq"},
        {"cargo": "REI"},
        {"ano": 1999},
        {"grupo": "mbl_2022"},  # grupo é de 2022, ano pedido 2026
        {"grupo": "inexistente"},
    ],
)
def test_mapa_parametros_invalidos(api: TestClient, extra: dict[str, object]) -> None:
    params = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026", **extra}
    params = {k: v for k, v in params.items() if v is not None}
    assert api.get("/api/mapa", params=params).status_code == 422


# ----------------------------------------------------------- /mapa/pontos
def test_pontos_densidade_ordenados_por_votos(api: TestClient) -> None:
    corpo = api.get(
        "/api/mapa/pontos", params={"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026"}
    ).json()
    assert corpo["total"] == 5
    assert corpo["truncado"] is False
    assert [p["votos"] for p in corpo["pontos"]] == [550, 300, 250, 40, 40]
    assert set(corpo["pontos"][0]) == {"lat", "lon", "votos"}
    assert corpo["pontos"][0]["lat"] == pytest.approx(-23.55)


def test_pontos_limite_e_offset(api: TestClient) -> None:
    base = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026"}
    pagina = api.get("/api/mapa/pontos", params={**base, "limite": 2}).json()
    assert [p["votos"] for p in pagina["pontos"]] == [550, 300]
    assert pagina["truncado"] is True
    resto = api.get("/api/mapa/pontos", params={**base, "limite": 2, "offset": 4}).json()
    assert [p["votos"] for p in resto["pontos"]] == [40]
    assert resto["truncado"] is False


@pytest.mark.parametrize("extra", [{"uf": None}, {"limite": 0}, {"limite": 50001}, {"grupo": None}])
def test_pontos_parametros_invalidos(api: TestClient, extra: dict[str, object]) -> None:
    params = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026", **extra}
    params = {k: v for k, v in params.items() if v is not None}
    assert api.get("/api/mapa/pontos", params=params).status_code == 422


# ---------------------------------------------------------------- /gastos
def test_gastos_do_grupo(api: TestClient) -> None:
    corpo = api.get("/api/gastos", params={"grupo": "missao_2026", "uf": "SP", "cargo": DF}).json()
    agg = corpo["agregado"]
    assert agg["despesa_contratada"] == 105000.0
    assert agg["despesa_paga"] == 85000.0
    assert agg["divida"] == 20000.0
    assert agg["votos"] == 1180
    assert agg["custo_voto_contratado"] == pytest.approx(105000 / 1180)
    assert agg["custo_voto_pago"] == pytest.approx(85000 / 1180)
    assert agg["mediana_custo_voto_contratado"] == pytest.approx((100.0 + 5000 / 180) / 2)
    assert agg["candidatos_sem_voto_excluidos"] == 0
    rec = corpo["receitas"]
    assert rec["receita_total"] == 125000.0
    assert rec["pct_publico"] == pytest.approx(100 * 80000 / 125000)
    assert rec["pct_autofinanciamento"] == pytest.approx(100 * 10000 / 125000)
    assert [c["sq_candidato"] for c in corpo["por_candidato"]] == [3, 5]
    assert corpo["contas_parciais"] is True
    assert corpo["dt_geracao"] == "2026-10-06"


def test_gastos_sem_filtros_inclui_todos_os_cargos(api: TestClient) -> None:
    corpo = api.get("/api/gastos", params={"grupo": "missao_2026"}).json()
    assert {c["sq_candidato"] for c in corpo["por_candidato"]} == {3, 4, 5}
    assert corpo["agregado"]["despesa_contratada"] == 107000.0


def test_gastos_2022_deflacionado(api: TestClient) -> None:
    corpo = api.get("/api/gastos", params={"grupo": "mbl_2022"}).json()
    assert corpo["base_ipca"] == "2026-09"
    assert corpo["agregado"]["despesa_contratada"] == pytest.approx(40000 * 1.005**48)
    assert corpo["contas_parciais"] is False


@pytest.mark.parametrize("params", [{}, {"grupo": "x"}, {"grupo": "missao_2026", "uf": "XX"}])
def test_gastos_parametros_invalidos(api: TestClient, params: dict[str, object]) -> None:
    assert api.get("/api/gastos", params=params).status_code == 422


# ------------------------------------------------------------ /comparativo
def _comparativo(api: TestClient, **extra: object) -> dict[str, object]:
    params = {"comparacao": "evolucao_mbl", "cargo": DF, "uf": "SP", **extra}
    r = api.get("/api/comparativo", params=params)
    assert r.status_code == 200, r.text
    corpo: dict[str, object] = r.json()
    return corpo


def test_comparativo_por_amc(api: TestClient) -> None:
    corpo = _comparativo(api)
    assert (corpo["n_de"], corpo["n_para"]) == (3, 3)
    assert corpo["mesmos_candidatos"] is False
    por_amc = {m["cd_amc"]: m for m in corpo["municipios"]}  # type: ignore[attr-defined]
    sp = por_amc[int(SP)]
    assert sp["penetracao_de"] == pytest.approx(1000 * 1000 / 14000)
    assert sp["penetracao_para"] == pytest.approx(1600 * 1000 / 15000)
    assert sp["delta_penetracao"] == pytest.approx(1600 * 1000 / 15000 - 1000 * 1000 / 14000)
    assert sp["swing_pp"] == pytest.approx(100 * 1600 / 10500 - 100 * 1000 / 10000)
    assert sp["retencao"] == pytest.approx(1.6)
    assert sp["ganho_absoluto"] == 600
    assert por_amc[int(SANTOS)]["retencao"] is None  # votos_2022 = 0 → null, não inf
    assert por_amc[int(SANTOS)]["delta_penetracao"] == pytest.approx(80.0)
    kpis = corpo["kpis"]
    assert isinstance(kpis, dict)
    assert kpis["penetracao_de"] == pytest.approx(1160 * 1000 / 16500)
    assert kpis["penetracao_para"] == pytest.approx(1880 * 1000 / 17500)
    assert kpis["ganho_absoluto"] == 720
    assert kpis["retencao"] == pytest.approx(1880 / 1160)


def test_comparativo_mesmos_candidatos(api: TestClient) -> None:
    corpo = _comparativo(api, mesmos_candidatos=True)
    assert (corpo["n_de"], corpo["n_para"]) == (2, 2)  # pessoas A e D
    por_amc = {m["cd_amc"]: m for m in corpo["municipios"]}  # type: ignore[attr-defined]
    assert por_amc[int(SP)]["ganho_absoluto"] == 1500 - 700
    assert por_amc[int(CAMP)]["retencao"] == pytest.approx(200 / 160)


@pytest.mark.parametrize(
    "extra",
    [
        {"comparacao": "inexistente"},
        {"cargo": "SENADOR"},  # 1 voto em 2022 × 2 em 2026: não comparável (spec 1.8)
        {"uf": "XX"},
        {"cargo": "REI"},
    ],
)
def test_comparativo_parametros_invalidos(api: TestClient, extra: dict[str, object]) -> None:
    params = {"comparacao": "evolucao_mbl", "cargo": DF, "uf": "SP", **extra}
    assert api.get("/api/comparativo", params=params).status_code == 422


# ----------------------------------------------------------- /municipios
def test_resumo_do_municipio(api: TestClient) -> None:
    corpo = api.get(f"/api/municipios/{SP}").json()
    assert (corpo["nome"], corpo["uf"]) == ("São Paulo", "SP")
    assert corpo["area_km2"] == pytest.approx(1521.11)
    grupos = {g["id"]: g for g in corpo["grupos"]}
    cargo = grupos["missao_2026"]["cargos"][0]
    assert cargo["cargo"] == DF
    assert cargo["votos"] == 1100
    assert cargo["aptos"] == 15000
    assert cargo["penetracao"] == pytest.approx(1100 * 1000 / 15000)
    assert cargo["pct_validos"] == pytest.approx(100 * 1100 / 10500)
    assert cargo["votos_por_km2"] == pytest.approx(1100 / 1521.11)
    assert grupos["mbl_2022"]["cargos"][0]["votos"] == 1000  # 500+200+300
    assert [c["cargo"] for c in grupos["missao_2026"]["cargos"]] == [DF]  # sq 4 é do RJ


@pytest.mark.parametrize(
    ("codigo", "status"), [("9999999", 404), ("abc", 422), ("123", 422), ("35503080", 422)]
)
def test_municipio_erros(api: TestClient, codigo: str, status: int) -> None:
    assert api.get(f"/api/municipios/{codigo}").status_code == status


# ------------------------------------------------------------ ETag / cache
def test_etag_e_cache_control_derivados_do_dt_geracao(api: TestClient) -> None:
    r = api.get("/api/candidatos", params={"grupo": "missao_2026"})
    assert r.status_code == 200
    etag = r.headers["etag"]
    assert etag.startswith('W/"') or etag.startswith('"')
    assert "max-age" in r.headers["cache-control"]
    r304 = api.get(
        "/api/candidatos", params={"grupo": "missao_2026"}, headers={"If-None-Match": etag}
    )
    assert r304.status_code == 304
    assert r304.content == b""
    assert r304.headers["etag"] == etag


def test_etag_muda_com_a_consulta_e_nao_cobre_health(api: TestClient) -> None:
    a = api.get("/api/candidatos", params={"grupo": "missao_2026"}).headers["etag"]
    b = api.get("/api/candidatos", params={"grupo": "mbl_2022"}).headers["etag"]
    assert a != b
    assert "etag" not in api.get("/api/health").headers
    obsoleto = api.get("/api/grupos", headers={"If-None-Match": '"outro-dt-geracao"'})
    assert obsoleto.status_code == 200


def test_erro_nao_recebe_etag(api: TestClient) -> None:
    r = api.get("/api/candidatos/2026/999")
    assert r.status_code == 404
    assert "etag" not in r.headers


def test_endpoints_de_dominio_sao_somente_leitura(api: TestClient) -> None:
    assert api.post("/api/grupos").status_code == 405


def test_partido_14_em_2022_nao_entra_no_grupo_da_missao(api: TestClient) -> None:
    """O nº 14 era PTB em 2022 (sq 10): grupo por partido vale só no ano do grupo."""
    missao = api.get("/api/candidatos", params={"grupo": "missao_2026"}).json()
    assert 10 not in {c["sq_candidato"] for c in missao["itens"]}
    assert {c["ano"] for c in missao["itens"]} == {2026}
    mbl22 = api.get("/api/candidatos", params={"grupo": "mbl_2022"}).json()
    assert 10 not in {c["sq_candidato"] for c in mbl22["itens"]}
