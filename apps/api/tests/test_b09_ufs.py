"""T-B09: UFs com candidaturas por ano/cargo/grupo (filtros dependentes do frontend)."""

from fastapi.testclient import TestClient


def _ufs(api: TestClient, **params: object) -> dict[str, int]:
    r = api.get("/api/candidatos/ufs", params=params)
    assert r.status_code == 200, r.text
    return {i["uf"]: i["candidaturas"] for i in r.json()["itens"]}


def test_presidente_so_tem_br(api: TestClient) -> None:
    assert _ufs(api, ano=2026, cargo="PRESIDENTE") == {"BR": 1}


def test_contagem_do_grupo_bate_com_n_candidaturas(api: TestClient) -> None:
    grupos = {g["id"]: g for g in api.get("/api/grupos").json()["grupos"]}
    for gid, g in grupos.items():
        assert sum(_ufs(api, grupo=gid).values()) == g["n_candidaturas"], gid


def test_grupo_restringe_e_define_ano(api: TestClient) -> None:
    com_grupo = _ufs(api, grupo="mbl_2022")
    todos_2022 = _ufs(api, ano=2022)
    assert com_grupo
    assert set(com_grupo) <= set(todos_2022)
    assert all(com_grupo[u] <= todos_2022[u] for u in com_grupo)


def test_ordenado_por_uf_e_com_dt_geracao(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/ufs", params={"ano": 2026}).json()
    ufs = [i["uf"] for i in corpo["itens"]]
    assert ufs == sorted(ufs)
    assert corpo["dt_geracao"]


def test_recorte_vazio_devolve_lista_vazia(api: TestClient) -> None:
    assert _ufs(api, ano=2022, cargo="PRESIDENTE") == {}


def test_exige_ano_ou_grupo(api: TestClient) -> None:
    assert api.get("/api/candidatos/ufs").status_code == 422


def test_grupo_e_ano_incompativeis(api: TestClient) -> None:
    r = api.get("/api/candidatos/ufs", params={"grupo": "mbl_2022", "ano": 2026})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "grupo_ano_incompativel"


def test_parametros_invalidos(api: TestClient) -> None:
    assert api.get("/api/candidatos/ufs", params={"ano": 2026, "cargo": "REI"}).status_code == 422
    assert api.get("/api/candidatos/ufs", params={"grupo": "x"}).status_code == 422


def test_cache_http(api: TestClient) -> None:
    r = api.get("/api/candidatos/ufs", params={"ano": 2026})
    assert r.headers.get("etag")
