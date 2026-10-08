"""T-B10: gastos por candidato com partido/resultado/%, `pessoas=` na evolução, varredura."""

import importlib.util
from pathlib import Path

import pytest
from api.pessoa import id_publico
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"


def _por_candidato(api: TestClient) -> dict[int, dict[str, object]]:
    r = api.get("/api/gastos", params={"grupo": "missao_2026", "uf": "SP", "cargo": DF})
    assert r.status_code == 200, r.text
    return {c["sq_candidato"]: c for c in r.json()["por_candidato"]}


def test_gastos_por_candidato_traz_partido_e_resultado(api: TestClient) -> None:
    cands = _por_candidato(api)
    assert cands
    cand = next(iter(cands.values()))
    ficha = api.get(f"/api/candidatos/2026/{cand['sq_candidato']}").json()["candidato"]
    assert cand["partido"] == ficha["partido"]
    assert cand["resultado"] == ficha["resultado"]


def test_gastos_por_candidato_pct_publico_e_autofinanciamento(api: TestClient) -> None:
    cands = _por_candidato(api)
    for c in cands.values():
        assert "pct_publico" in c
        assert "pct_autofinanciamento" in c
    # sq 3 recebeu receitas na fixture: o % é calculado sobre a receita do próprio candidato
    com_receita = [c for c in cands.values() if c["receita_total"]]
    assert com_receita
    for c in com_receita:
        assert c["pct_publico"] is not None
        assert 0 <= c["pct_publico"] <= 100  # type: ignore[operator]
        assert 0 <= c["pct_autofinanciamento"] <= 100  # type: ignore[operator]


def test_evolucao_pessoas_traz_escolhidas_fora_da_pagina(api: TestClient) -> None:
    todas = api.get("/api/evolucao/pessoas").json()["itens"]
    assert len(todas) >= 3
    ultima = todas[-1]["pessoa_id_publico"]
    pagina = api.get("/api/evolucao/pessoas", params={"limite": 1}).json()["itens"]
    assert ultima not in {i["pessoa_id_publico"] for i in pagina}
    r = api.get("/api/evolucao/pessoas", params={"limite": 1, "pessoas": [ultima]})
    assert r.status_code == 200, r.text
    ids = [i["pessoa_id_publico"] for i in r.json()["itens"]]
    assert ultima in ids
    assert len(ids) == len(set(ids)) == 2  # página + escolhida, sem duplicar


def test_evolucao_pessoas_escolhida_ja_na_pagina_nao_duplica(api: TestClient) -> None:
    primeira = api.get("/api/evolucao/pessoas").json()["itens"][0]["pessoa_id_publico"]
    itens = api.get("/api/evolucao/pessoas", params={"limite": 1, "pessoas": [primeira]}).json()[
        "itens"
    ]
    assert [i["pessoa_id_publico"] for i in itens] == [primeira]


def test_evolucao_pessoas_id_invalido_e_desconhecido(api: TestClient) -> None:
    assert api.get("/api/evolucao/pessoas", params={"pessoas": ["x"]}).status_code == 422
    inexistente = id_publico("ninguem")
    r = api.get("/api/evolucao/pessoas", params={"pessoas": [inexistente]})
    assert r.status_code == 200
    assert inexistente not in {i["pessoa_id_publico"] for i in r.json()["itens"]}


def test_varredura_cobre_candidatos_ufs() -> None:
    spec = importlib.util.spec_from_file_location(
        "varredura", Path(__file__).parents[1] / "scripts" / "varredura.py"
    )
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    gerados = list(modulo.pedidos(_get_falso(modulo)))
    caminhos = {c for c, _ in gerados}
    assert "/api/candidatos/ufs" in caminhos


def _get_falso(modulo: object) -> object:
    grupos = {
        "grupos": [{"id": "g", "ano": 2026}],
        "comparacoes": [],
    }

    def get(caminho: str, params: dict[str, object]) -> tuple[int, object, float]:
        if caminho == "/api/grupos":
            return 200, grupos, 0.0
        return 200, {"itens": []}, 0.0

    return get


pytestmark = pytest.mark.filterwarnings("ignore")
