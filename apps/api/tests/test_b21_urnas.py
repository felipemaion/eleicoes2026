"""T-B21: só candidaturas que foram às urnas entram em contagens, listas e médias.

Mundo da fixture: sq 40 é registro substituído da pessoa B (sq 5 foi às urnas) — Missão,
Dep. Federal/SP, sem situação (2026 chega `#NE`) e sem resultado. Todo número público tem de
sair como se o sq 40 não existisse; só a ficha por sq o mostra.
"""

from typing import Any

from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"
SP_MUN = 3550308


def _json(api: TestClient, caminho: str, **p: object) -> Any:
    r = api.get(caminho, params=p)  # type: ignore[arg-type]
    assert r.status_code == 200, r.text
    return r.json()


def _sqs(corpo: dict[str, Any]) -> list[int]:
    return [i["sq_candidato"] for i in corpo["itens"]]


def test_ficha_do_registro_fora_da_urna_continua_acessivel_e_diz_o_porque(api: TestClient) -> None:
    ficha = _json(api, "/api/candidatos/2026/40")
    assert ficha["candidato"]["foi_as_urnas"] is False
    assert ficha["candidato"]["situacao"] == "Não foi às urnas"
    assert _json(api, "/api/candidatos/2026/5")["candidato"]["foi_as_urnas"] is True


def test_listas_e_busca_nao_trazem_o_registro_fora_da_urna(api: TestClient) -> None:
    lista = _json(api, "/api/candidatos", grupo="missao_2026", ano=2026, cargo=DF, uf="SP")
    assert 40 not in _sqs(lista)
    assert all(i["foi_as_urnas"] for i in lista["itens"])
    achados = _json(api, "/api/busca", q="bruno", ano=2026)
    assert [i["sq_candidato"] for i in achados["itens"]] == [5]


def test_contagens_de_candidaturas_ignoram_o_registro_fora_da_urna(api: TestClient) -> None:
    grupos = {g["id"]: g for g in _json(api, "/api/grupos")["grupos"]}
    assert grupos["missao_2026"]["n_candidaturas"] == 3
    muni = _json(api, f"/api/municipios/{SP_MUN}")
    missao = next(g for g in muni["grupos"] if g["id"] == "missao_2026")
    assert [c["n_candidaturas"] for c in missao["cargos"] if c["cargo"] == DF] == [2]
    mapa = _json(api, "/api/mapa", grupo="missao_2026", ano=2026, cargo=DF, uf="SP")
    assert mapa["n_candidaturas"] == 2


def test_comparativo_conta_uma_candidatura_por_pessoa(api: TestClient) -> None:
    c = _json(
        api, "/api/comparativo", cargo=DF, uf="SP", grupo_2022="mbl_2022", grupo_2026="missao_2026"
    )
    assert c["n_para"] == 2
