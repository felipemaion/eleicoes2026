"""T-B07: busca de candidaturas, evolução por pessoa e comparativo de seleção."""

from typing import Any

from api.pessoa import id_publico
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"


def _sqs(api: TestClient, **params: object) -> list[int]:
    r = api.get("/api/busca", params=params)
    assert r.status_code == 200, r.text
    return [i["sq_candidato"] for i in r.json()["itens"]]


def test_busca_por_nome_civil_sem_acento_e_case_insensitive(api: TestClient) -> None:
    assert sorted(_sqs(api, q="cesar")) == [2, 4]
    assert sorted(_sqs(api, q="CÉSAR")) == [2, 4]


def test_busca_prefixo_vem_antes_de_substring(api: TestClient) -> None:
    # "ana" é prefixo de "ANA ALVES" (1, 3) e não aparece em outros nomes de urna/civil
    assert sorted(_sqs(api, q="ana")) == [1, 3]
    # "alves" é só substring de "ANA ALVES DA SILVA"
    assert sorted(_sqs(api, q="alves")) == [1, 3]
    # prefixo (DANIEL) antes de substring ("ESTÊVÃO" não contém "dan"; "RAMOS" não)
    assert set(_sqs(api, q="dan")) == {7, 9}


def test_busca_por_nome_de_urna(api: TestClient) -> None:
    assert _sqs(api, q="a 2022") == [1]


def test_busca_por_numero_e_por_partido(api: TestClient) -> None:
    assert _sqs(api, q="1415")[0] == 3
    assert set(_sqs(api, q="missao", ano=2026)) == {3, 4, 5}
    assert set(_sqs(api, q="MISSÃO", ano=2026)) == {3, 4, 5}
    # "14" = número do partido (3, 4, 5) ou prefixo de número de candidato
    assert {3, 4, 5} <= set(_sqs(api, q="14", ano=2026))


def test_busca_filtros(api: TestClient) -> None:
    assert set(_sqs(api, q="ana", ano=2026)) == {3}
    assert set(_sqs(api, q="ana", cargo=DF, uf="SP")) == {1, 3}
    assert _sqs(api, q="cesar", uf="SP") == []
    assert set(_sqs(api, q="ana", grupo="mbl_2022")) == {1}


def test_busca_limite(api: TestClient) -> None:
    r = api.get("/api/busca", params={"q": "ana", "limite": 1}).json()
    assert len(r["itens"]) == 1
    assert r["total"] == 2


def test_busca_item_completo_sem_pii(api: TestClient) -> None:
    item = api.get("/api/busca", params={"q": "ana", "ano": 2026}).json()["itens"][0]
    assert item["ano"] == 2026
    assert item["nm_urna"] == "A"
    assert item["numero"] == 1415
    assert item["cargo"] == DF
    assert item["uf"] == "SP"
    assert item["partido"] == {"numero": 14, "sigla": "MISSÃO"}
    assert item["votos"] == 1000
    assert item["resultado"] == "SUPLENTE"
    assert item["indicado"] is True  # linha origem=indicado da lista de referência (2026)
    assert item["abrangencia"] == {"tipo": "uf", "uf": "SP"}
    assert item["pessoa_id_publico"] == id_publico("pA")
    assert len(item["pessoa_id_publico"]) == 12
    assert "pessoa_id" not in item
    assert "pA" not in str(item.values())


def test_busca_indicado_e_abrangencia_do_presidente(api: TestClient) -> None:
    indicado = api.get("/api/busca", params={"q": "ana", "ano": 2022}).json()["itens"][0]
    assert indicado["indicado"] is True
    pres = api.get("/api/busca", params={"q": "paulo"}).json()["itens"][0]
    assert pres["abrangencia"] == {"tipo": "pais", "uf": None}
    assert pres["uf"] == "BR"


def test_busca_valida_parametros(api: TestClient) -> None:
    assert api.get("/api/busca").status_code == 422
    assert api.get("/api/busca", params={"q": ""}).status_code == 422
    assert api.get("/api/busca", params={"q": "a", "uf": "XX"}).status_code == 422
    assert api.get("/api/busca", params={"q": "a", "limite": 1000}).status_code == 422
    assert api.get("/api/busca", params={"q": "a", "grupo": "nao_existe"}).status_code == 422


def test_busca_trata_curingas_e_injecao_como_texto(api: TestClient) -> None:
    for q in ("%", "_", "'; DROP VIEW candidatos; --", "\\"):
        r = api.get("/api/busca", params={"q": q})
        assert r.status_code == 200, (q, r.text)
        assert r.json()["itens"] == []


# ------------------------------------------------------------- evolução por pessoa
def test_evolucao_pessoas_lista_quem_esta_nos_dois_anos(api: TestClient) -> None:
    r = api.get("/api/evolucao/pessoas")
    assert r.status_code == 200, r.text
    itens = r.json()["itens"]
    assert {i["pessoa_id_publico"] for i in itens} == {
        id_publico("pA"),
        id_publico("pC"),
        id_publico("pD"),
    }
    a = next(i for i in itens if i["pessoa_id_publico"] == id_publico("pA"))
    assert (a["de"]["ano"], a["de"]["sq_candidato"], a["de"]["votos"]) == (2022, 1, 800)
    assert (a["para"]["ano"], a["para"]["sq_candidato"]) == (2026, 3)
    assert a["para"]["votos"] == 1000
    assert a["mesmo_cargo"] is True
    assert "pessoa_id" not in a


def test_evolucao_pessoas_filtros(api: TestClient) -> None:
    def ids(**p: object) -> set[str]:
        r = api.get("/api/evolucao/pessoas", params=p)
        assert r.status_code == 200, r.text
        return {i["pessoa_id_publico"] for i in r.json()["itens"]}

    assert ids(q="ana") == {id_publico("pA")}
    assert ids(uf="RJ") == {id_publico("pC")}
    assert ids(cargo=DF) == {id_publico("pA"), id_publico("pD")}
    assert ids(q="zzzz") == set()


# ------------------------------------------------- comparativo de seleção do usuário
def _kpis(api: TestClient, **p: object) -> dict[str, Any]:
    r = api.get("/api/comparativo", params={"cargo": DF, **p})
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def test_comparativo_por_pessoas_e_por_sqs_dao_o_mesmo(api: TestClient) -> None:
    por_pessoa = _kpis(api, pessoas=id_publico("pA"))
    por_sq = _kpis(api, sq_2022=1, sq_2026=3)
    assert por_pessoa["kpis"] == por_sq["kpis"]
    assert por_pessoa["kpis"]["votos_de"] == 800
    assert por_pessoa["kpis"]["votos_para"] == 1000
    assert por_pessoa["comparacao"] == "selecao"
    assert (por_pessoa["de"]["ano"], por_pessoa["para"]["ano"]) == (2022, 2026)
    assert (por_pessoa["n_de"], por_pessoa["n_para"]) == (1, 1)


def test_comparativo_com_varias_pessoas_soma_a_selecao(api: TestClient) -> None:
    c = _kpis(api, pessoas=[id_publico("pA"), id_publico("pD")])
    assert c["kpis"]["votos_de"] == 800 + 60
    assert c["kpis"]["votos_para"] == 1000 + 700


def test_comparativo_selecao_exige_um_modo(api: TestClient) -> None:
    r = api.get("/api/comparativo", params={"cargo": DF})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "comparativo_sem_alvo"
    r = api.get(
        "/api/comparativo",
        params={"cargo": DF, "comparacao": "evolucao_mbl", "pessoas": id_publico("pA")},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "comparacao_e_selecao"


def test_comparativo_selecao_sem_par_e_422(api: TestClient) -> None:
    r = api.get("/api/comparativo", params={"cargo": DF, "pessoas": "0123456789ab"})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "sem_par_comparavel"


def test_id_publico_nao_e_o_pessoa_id() -> None:
    assert id_publico("pA") != "pA"
    assert id_publico("pA") == id_publico("pA")
    assert id_publico("pA") != id_publico("pB")
