"""T-B16: validação mais dura do comparativo por lado (revisão da T-B15)."""

from typing import Any

import pytest
from api.repositorio.modelos import Candidatura
from api.servicos.comparativo import n_em_disputa
from fastapi.testclient import TestClient

DF = "DEPUTADO FEDERAL"


def _get(api: TestClient, **p: object) -> Any:
    return api.get("/api/comparativo", params={"cargo": DF, "uf": "SP", **p})


@pytest.mark.parametrize(
    ("params", "sqs"),
    [
        ({"sq_2022": 2, "grupo_2026": "missao_2026"}, [2]),  # RJ / Dep. Estadual
        ({"sq_2022": [1, 2], "grupo_2026": "missao_2026"}, [2]),
        ({"grupo_2022": "mbl_2022", "sq_2026": 4}, [4]),  # outro cargo/UF
        ({"grupo_2022": "mbl_2022", "sq_2026": 11}, [11]),  # Presidente
    ],
)
def test_sq_fora_do_recorte_e_422_listando_os_sq(
    api: TestClient, params: dict[str, object], sqs: list[int]
) -> None:
    r = _get(api, **params)
    assert r.status_code == 422, r.text
    detalhe = r.json()["detail"]
    assert detalhe["codigo"] == "sq_fora_do_recorte"
    for sq in sqs:
        assert str(sq) in detalhe["mensagem"]


def test_sq_de_outro_ano_e_422_nao_some(api: TestClient) -> None:
    """sq 3 existe só em 2026: pedido como sq_2022 é 404 (não existe naquele ano)."""
    assert _get(api, sq_2022=3, grupo_2026="missao_2026").status_code == 404


def test_grupo_invalido_vence_sq_inexistente(api: TestClient) -> None:
    """Grupos são validados antes de consultar o repositório pelos sq."""
    r = _get(api, sq_2022=999999, grupo_2026="inexistente")
    assert r.status_code in (404, 422)
    assert r.json()["detail"]["codigo"] == "grupo_desconhecido"
    r = _get(api, sq_2026=999999, grupo_2022="missao_2026")
    assert r.json()["detail"]["codigo"] == "grupo_ano_errado"


def test_mesmos_candidatos_em_lado_misto_e_422(api: TestClient) -> None:
    r = _get(api, sq_2022=1, grupo_2026="missao_2026", mesmos_candidatos="true")
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "mesmos_candidatos_lado_misto"


def test_mesmos_candidatos_com_dois_grupos_continua_valendo(api: TestClient) -> None:
    r = _get(api, grupo_2022="mbl_2022", grupo_2026="mbl_2026", mesmos_candidatos="true")
    assert r.status_code == 200, r.text


def _cand(sq: int, situacao: str | None) -> Candidatura:
    return Candidatura(
        ano=2026, sq_candidato=sq, pessoa_id=f"p{sq}", nm_urna="X", sg_uf="SP",
        ds_cargo="DEPUTADO FEDERAL", nr_partido=14, sg_partido="MISSÃO",
        ds_situacao_candidatura=situacao, ds_sit_tot_turno=None,
    )  # fmt: skip


def test_n_em_disputa_conta_aptas_e_sem_situacao_mas_nao_indeferidas() -> None:
    lado = [_cand(1, "APTO"), _cand(2, None), _cand(3, "INDEFERIDO"), _cand(4, "RENÚNCIA")]
    assert n_em_disputa(lado) == 2


def test_n_em_disputa_lado_vazio_e_zero() -> None:
    assert n_em_disputa([]) == 0
