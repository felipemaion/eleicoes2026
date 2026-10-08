"""T-B15: comparativo por lado (grupo ou candidatos, independentes) e `n_para` preenchido.

DuckDB real sobre as fixtures Parquet. Números: sq 1 (2022, pessoa A) 800 votos; sq 9 (pD) 60;
Missão 2026 em Dep. Federal/SP = sq 3 (1000) + sq 5 (180).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"


def _get(api: TestClient, **p: object) -> Any:
    return api.get("/api/comparativo", params={"cargo": DF, "uf": "SP", **p})


def _ok(api: TestClient, **p: object) -> dict[str, Any]:
    r = _get(api, **p)
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def test_candidatos_2022_contra_grupo_2026(api: TestClient) -> None:
    c = _ok(api, sq_2022=[1, 9], grupo_2026="missao_2026")
    assert c["kpis"]["votos_de"] == 800 + 60
    assert c["kpis"]["votos_para"] == 1180
    assert (c["n_de"], c["n_para"]) == (2, 2)
    assert c["comparacao"] == "selecao"
    assert (c["de"]["id"], c["para"]["id"]) == ("selecao", "missao_2026")
    assert c["receitas"] is not None


def test_grupo_2022_contra_candidatos_2026(api: TestClient) -> None:
    c = _ok(api, grupo_2022="mbl_2022", sq_2026=3)
    assert c["kpis"]["votos_para"] == 1000
    assert c["de"]["id"] == "mbl_2022"
    assert (c["n_de"], c["n_para"]) == (3, 1)


def test_dois_grupos_por_lado_equivale_a_comparacao(api: TestClient) -> None:
    por_lado = _ok(api, grupo_2022="mbl_2022", grupo_2026="mbl_2026")
    atalho = _ok(api, comparacao="evolucao_mbl")
    assert por_lado["kpis"] == atalho["kpis"]
    assert por_lado["municipios"] == atalho["municipios"]


def test_rotulo_descreve_os_lados(api: TestClient) -> None:
    c = _ok(api, sq_2022=[1, 9], grupo_2026="missao_2026")
    assert c["rotulo"] == "A 2022 + D 2022 (2022) → Partido Missão 2026"
    c = _ok(api, grupo_2022="mbl_2022", sq_2026=3)
    assert c["rotulo"] == "MBL 2022 → A (2026)"


def test_municipios_e_receitas_do_lado_misto(api: TestClient) -> None:
    c = _ok(api, sq_2022=1, grupo_2026="missao_2026")
    por_amc = {m["cd_amc"]: m for m in c["municipios"]}
    assert por_amc[3550308]["votos_de"] == 700
    assert por_amc[3550308]["votos_para"] == 1100
    assert por_amc[3509502]["votos_para"] == 40
    assert c["receitas"]["monetarios"]["receita_total"]["de_nominal"] == 40000.0


@pytest.mark.parametrize(
    ("params", "codigo"),
    [
        ({"sq_2022": 1}, "lado_vazio"),
        ({"grupo_2026": "missao_2026"}, "lado_vazio"),
        ({"sq_2022": 1, "grupo_2022": "mbl_2022", "grupo_2026": "missao_2026"}, "lado_ambiguo"),
        ({"sq_2026": 3, "grupo_2026": "missao_2026", "sq_2022": 1}, "lado_ambiguo"),
        ({"grupo_2022": "missao_2026", "grupo_2026": "missao_2026"}, "grupo_ano_errado"),
        ({"grupo_2022": "mbl_2022", "grupo_2026": "mbl_2022"}, "grupo_ano_errado"),
        ({"grupo_2022": "inexistente", "grupo_2026": "missao_2026"}, "grupo_desconhecido"),
        ({"comparacao": "evolucao_mbl", "grupo_2026": "missao_2026"}, "comparacao_e_selecao"),
        ({"comparacao": "evolucao_mbl", "sq_2022": 1}, "comparacao_e_selecao"),
        ({"sq_2022": 1, "grupo_2026": "missao_2026", "pessoas": "0123456789ab"}, "lado_ambiguo"),
    ],
)
def test_combinacoes_invalidas_sao_422_com_codigo(
    api: TestClient, params: dict[str, object], codigo: str
) -> None:
    r = _get(api, **params)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == codigo


def test_sq_inexistente_no_lado_e_404(api: TestClient) -> None:
    assert _get(api, sq_2022=999999, grupo_2026="missao_2026").status_code == 404


def test_n_para_traz_as_candidaturas_de_2026(api: TestClient) -> None:
    """Regressão: vinha null em toda resposta de 2026 (situação ainda não publicada)."""
    c = _ok(api, comparacao="evolucao_mbl")
    assert c["n_para"] == 3
    assert c["n_de"] == 3
    assert _ok(api, sq_2022=1, sq_2026=3)["n_para"] == 1
