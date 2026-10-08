"""T-B07: presidente sem erro (exterior sem município), pontos nacionais e comparativo sem par.

Fixture: sq 11 (NOVO, nº 30, Presidente) tem 3000 votos em SP, 500 em Campinas e 200 no
exterior (`cd_mun_ibge` nulo). O grupo `novo_2026` (partido 30) faz o papel do Missão na produção.
"""

import pytest
from fastapi.testclient import TestClient

PR = "PRESIDENTE"


@pytest.mark.parametrize(
    "alvo", [{"grupo": "novo_2026"}, {"sq_candidato": 11}], ids=["grupo", "candidato"]
)
def test_mapa_presidente_exclui_exterior_e_informa(
    api: TestClient, alvo: dict[str, object]
) -> None:
    r = api.get("/api/mapa", params={"ano": 2026, "cargo": PR, "indicador": "votos", **alvo})
    assert r.status_code == 200, r.text
    corpo = r.json()
    # Municípios com eleitorado entram (Santos e Rio com 0 voto); "None" nunca vira chave.
    assert set(corpo["valores"]) == {"3550308", "3509502", "3548500", "3304557"}
    assert corpo["valores"]["3550308"] == 3000
    assert corpo["valores"]["3548500"] == 0
    assert corpo["votos_fora_do_mapa"] == 200


def test_mapa_com_uf_nao_tem_voto_fora_do_mapa(api: TestClient) -> None:
    r = api.get("/api/mapa", params={"ano": 2026, "cargo": PR, "uf": "SP", "sq_candidato": 11})
    assert r.status_code == 200, r.text
    assert r.json()["votos_fora_do_mapa"] == 0


def test_mapa_zona_presidente_sem_erro(api: TestClient) -> None:
    r = api.get(
        "/api/mapa",
        params={"ano": 2026, "cargo": PR, "uf": "SP", "nivel": "zona", "sq_candidato": 11},
    )
    assert r.status_code == 200, r.text


def test_ficha_do_presidente_inclui_exterior(api: TestClient) -> None:
    r = api.get("/api/candidatos/2026/11")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["votos_total"] == 3700
    assert {"uf": "ZZ", "votos": 200} in corpo["votos_por_uf"]
    assert {u["uf"] for u in corpo["votos_por_municipio"]} == {"SP"}
    assert corpo["candidato"]["abrangencia"] == {"tipo": "pais", "uf": None}


def test_candidatos_do_grupo_com_presidente(api: TestClient) -> None:
    r = api.get("/api/candidatos", params={"grupo": "novo_2026", "cargo": PR})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["itens"][0]["votos"] == 3700
    assert corpo["itens"][0]["abrangencia"] == {"tipo": "pais", "uf": None}
    assert corpo["kpis"]["votos"] == 3700


def test_comparativo_de_presidente_sem_par_comparavel_e_422(api: TestClient) -> None:
    r = api.get("/api/comparativo", params={"comparacao": "evolucao_mbl", "cargo": PR})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "sem_par_comparavel"


def test_pontos_do_presidente_sem_uf_agrega_em_grade(api: TestClient) -> None:
    r = api.get("/api/mapa/pontos", params={"ano": 2026, "cargo": PR, "sq_candidato": 11})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["grade_graus"] == 0.1
    assert corpo["total"] == 2  # SP (2 locais na mesma célula) e Campinas
    assert [p["votos"] for p in corpo["pontos"]] == [3000, 500]
    assert corpo["pontos"][0]["lat"] == pytest.approx(-23.5533, abs=1e-3)
    assert corpo["votos_sem_coordenada"] == 0


def test_pontos_com_uf_continua_ponto_a_ponto(api: TestClient) -> None:
    r = api.get(
        "/api/mapa/pontos", params={"ano": 2026, "cargo": PR, "uf": "SP", "sq_candidato": 11}
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["grade_graus"] is None
    assert corpo["total"] == 3  # um ponto por local de votação
