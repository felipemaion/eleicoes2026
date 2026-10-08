"""T-B14: indicadores de receita (T-A08) expostos em /gastos, na ficha e no /comparativo.

Números da fixture (missao_2026, SP, deputado federal = candidatos 3 e 5): receita bruta 100000
e 25000; o repasse de 7000 do sq 5 ao sq 3 sai do total do grupo (118000). Votos 1000 e 180.
Despesa contratada 100000 (+400 de repasse) e 5000.
"""

import pytest
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"
PARAMS = {"grupo": "missao_2026", "uf": "SP", "cargo": DF}
FATOR = 1.005**48  # IPCA fixture: 2022-09 → 2026-09


def _gastos(api: TestClient) -> dict:  # type: ignore[type-arg]
    return api.get("/api/gastos", params=PARAMS).json()


def test_receitas_do_grupo_trazem_composicao_e_repasses(api: TestClient) -> None:
    rec = _gastos(api)["receitas"]
    assert rec["receita_total"] == 118000.0
    assert rec["receita_estimavel"] == 0.0
    assert rec["receita_repasses_internos"] == 7000.0
    assert rec["receita_repasses_doador_desconhecido"] == 0.0
    assert rec["faixa_receita"] == {"minima": 118000.0, "maxima": 118000.0}
    assert rec["pct_pessoa_fisica"] == pytest.approx(100 * (15000 + 2000 + 8000) / 118000)
    assert rec["pct_estimavel"] == 0.0
    assert rec["n_efetivo_fontes"] > 1
    assert rec["hhi_fontes"] == pytest.approx(1 / rec["n_efetivo_fontes"])


def test_receita_por_voto_e_distribuicao_do_grupo(api: TestClient) -> None:
    corpo = _gastos(api)
    por_voto = corpo["receita_por_voto"]
    assert por_voto["receita_por_voto"] == pytest.approx(118000 / 1180)  # Σ/Σ, sem repasse interno
    assert por_voto["mediana_receita_por_voto"] == pytest.approx((93000 / 1000 + 25000 / 180) / 2)
    assert por_voto["candidatos_sem_voto_excluidos"] == 0
    dist = corpo["distribuicao_receita"]
    assert dist["n_candidatos"] == 2
    assert dist["n_com_contas"] == 2
    assert dist["soma"] == 118000.0
    assert dist["media"] == 59000.0
    assert dist["mediana"] == 59000.0
    assert dist["maximo"] == 93000.0


def test_saldo_do_grupo_usa_despesa_com_repasses(api: TestClient) -> None:
    saldo = _gastos(api)["saldo"]
    # receita bruta 125000 − (105000 própria + 400 repasse): repasses internos se anulam.
    assert saldo["saldo_contratado"] == pytest.approx(125000 - 105400)
    assert saldo["saldo_financeiro"] == pytest.approx(125000 - 85400)
    assert saldo["pct_receita_gasta"] == pytest.approx(100 * 105400 / 125000)


def test_receita_por_mil_aptos_do_grupo(api: TestClient) -> None:
    corpo = _gastos(api)
    assert corpo["receita_por_mil_aptos"] == pytest.approx(1000 * 118000 / corpo["aptos"])
    assert corpo["aptos"] > 0


def test_por_mil_aptos_nulo_com_varios_cargos(api: TestClient) -> None:
    corpo = api.get("/api/gastos", params={"grupo": "missao_2026"}).json()
    assert corpo["receita_por_mil_aptos"] is None  # eleitorado de cargos diferentes não se soma
    assert corpo["aptos"] is None


def test_candidato_do_grupo_tem_receita_por_voto_e_saldo(api: TestClient) -> None:
    por_sq = {c["sq_candidato"]: c for c in _gastos(api)["por_candidato"]}
    c3 = por_sq[3]
    assert c3["receita_total"] == 100000.0
    assert c3["receita_por_voto"] == pytest.approx(100.0)
    assert c3["saldo_contratado"] == pytest.approx(100000 - 100400)
    assert c3["pct_receita_gasta"] == pytest.approx(100 * 100400 / 100000)
    assert c3["receita_por_mil_aptos"] is not None
    assert c3["pct_pessoa_fisica"] == pytest.approx(25000 / 1000)  # (15+2+8) mil de 100 mil
    assert c3["receita_repasses_candidatos"] == 7000.0
    assert c3["receita_sem_repasses"] == 93000.0


def test_ficha_tem_os_mesmos_campos(api: TestClient) -> None:
    corpo = api.get("/api/candidatos/2026/3").json()
    g = corpo["gastos"]
    assert g["receita_por_voto"] == pytest.approx(100.0)
    assert g["saldo_contratado"] == pytest.approx(100000 - 100400)
    assert g["pct_receita_gasta"] == pytest.approx(100.4)
    rec = corpo["receitas"]
    assert rec["receita_repasses_candidatos"] == 7000.0
    assert rec["pct_pessoa_fisica"] == pytest.approx(25.0)


def test_comparativo_traz_receitas_2022_deflacionadas(api: TestClient) -> None:
    corpo = api.get(
        "/api/comparativo", params={"comparacao": "evolucao_mbl", "cargo": DF, "uf": "SP"}
    ).json()
    rec = corpo["receitas"]
    assert rec["base_ipca"] == "2026-09"
    total = rec["monetarios"]["receita_total"]
    assert total["de_nominal"] == 40000.0
    assert total["de"] == pytest.approx(40000 * FATOR)
    assert total["para"] == 100000.0
    assert total["delta"] == pytest.approx(100000 - 40000 * FATOR)
    assert total["var_pct"] == pytest.approx(100 * (100000 / (40000 * FATOR) - 1))
    pub = rec["percentuais"]["pct_publico"]
    assert pub["de"] == pytest.approx(75.0)  # 30000 FEFC de 40000
    assert pub["delta"] == pytest.approx(pub["para"] - pub["de"])
    assert rec["contas_parciais_para"] is True
    assert any(f["id"] == "ipca" for f in corpo["fontes"])


def test_comparativo_de_selecao_tambem_traz_receitas(api: TestClient) -> None:
    corpo = api.get(
        "/api/comparativo", params={"cargo": DF, "uf": "SP", "sq_2022": 1, "sq_2026": 3}
    ).json()
    assert corpo["receitas"]["monetarios"]["receita_total"]["para"] == 100000.0


def test_openapi_documenta_os_campos_novos(api: TestClient) -> None:
    esquemas = api.get("/api/openapi.json").json()["components"]["schemas"]
    assert "receita_por_voto" in esquemas["Gastos"]["properties"]
    assert "receitas" in esquemas["Comparativo"]["properties"]
    assert "saldo_contratado" in esquemas["GastoCandidato"]["properties"]
