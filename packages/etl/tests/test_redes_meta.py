"""Cliente da Graph API (Business Discovery) sobre respostas sintéticas — sem rede."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from etl.redes.meta import (
    ClienteMeta,
    ErroLimite,
    ErroMeta,
    PerfilIndisponivel,
    aviso_de_vencimento,
)

TOKEN = "EAAB-token-secreto-123"


def _cliente(
    handler: Callable[[httpx.Request], httpx.Response], dormidos: list[float] | None = None
) -> ClienteMeta:
    dormidos = dormidos if dormidos is not None else []
    return ClienteMeta(
        TOKEN,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        dormir=dormidos.append,
        espera_base=10.0,
        max_tentativas=3,
    )


def _erro(code: int, subcode: int | None = None, status: int = 400) -> httpx.Response:
    corpo: dict[str, object] = {"message": "boom", "type": "OAuthException", "code": code}
    if subcode is not None:
        corpo["error_subcode"] = subcode
    return httpx.Response(status, json={"error": corpo})


def test_descobre_a_conta_instagram_sem_id_fixo() -> None:
    vistos: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(req)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "1", "name": "sem ig"},
                    {"id": "2", "instagram_business_account": {"id": "17841"}},
                ]
            },
        )

    assert _cliente(handler).conta_instagram() == "17841"
    assert vistos[0].url.path == "/v26.0/me/accounts"
    assert vistos[0].url.params["fields"] == "instagram_business_account"


def test_sem_conta_instagram_vinculada_falha_alto() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    with pytest.raises(ErroMeta, match="instagram_business_account"):
        _cliente(handler).conta_instagram()


def test_token_vai_no_cabecalho_e_nunca_na_url_nem_na_mensagem_de_erro() -> None:
    vistos: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(req)
        return _erro(190, status=401)

    with pytest.raises(ErroMeta) as e:
        _cliente(handler).business_discovery("17841", "kimkataguiri")
    assert TOKEN not in str(vistos[0].url)
    assert vistos[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(e.value)
    assert TOKEN not in repr(_cliente(handler))


def test_pagina_do_perfil_com_curtida_oculta_nula() -> None:
    vistos: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(req)
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "username": "kim",
                    "followers_count": 10,
                    "follows_count": 2,
                    "media_count": 5,
                    "media": {
                        "data": [
                            {
                                "id": "m1",
                                "timestamp": "2026-10-01T12:00:00+0000",
                                "media_type": "VIDEO",
                                "media_product_type": "REELS",
                                "comments_count": 3,
                                "permalink": "https://www.instagram.com/reel/x/",
                            }
                        ],
                        "paging": {"cursors": {"after": "CUR2"}, "next": "https://..."},
                    },
                }
            },
        )

    pag = _cliente(handler).business_discovery("17841", "kim", cursor="CUR1")
    campos = vistos[0].url.params["fields"]
    assert "business_discovery.username(kim)" in campos
    assert "media.limit(50).after(CUR1)" in campos
    assert pag.seguidores == 10
    assert pag.proximo == "CUR2"
    [m] = pag.midias
    assert m["like_count"] is None  # oculta → nulo, nunca zero
    assert m["timestamp"] == datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert m["comments_count"] == 3


def test_ultima_pagina_nao_tem_proximo() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "username": "kim",
                    "followers_count": 1,
                    "follows_count": 1,
                    "media_count": 0,
                    "media": {"data": []},
                }
            },
        )

    pag = _cliente(handler).business_discovery("17841", "kim")
    assert pag.proximo is None
    assert pag.midias == []


@pytest.mark.parametrize("code", [110, 100])
def test_perfil_inexistente_ou_pessoal_vira_status_sem_derrubar(code: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _erro(code, 2207013)

    with pytest.raises(PerfilIndisponivel) as e:
        _cliente(handler).business_discovery("17841", "fulano")
    assert e.value.status == "nao_encontrado"


def test_mensagem_de_conta_nao_comercial_vira_nao_comercial() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 110,
                    "error_subcode": 2207013,
                    "error_user_msg": "O perfil não é uma conta comercial ou de criador.",
                }
            },
        )

    with pytest.raises(PerfilIndisponivel) as e:
        _cliente(handler).business_discovery("17841", "fulano")
    assert e.value.status == "nao_comercial"


@pytest.mark.parametrize("code", [190, 102, 10, 200, 299])
def test_token_e_permissao_falham_alto(code: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _erro(code)

    with pytest.raises(ErroMeta) as e:
        _cliente(handler).business_discovery("17841", "fulano")
    assert not isinstance(e.value, PerfilIndisponivel)


def test_limite_de_chamadas_espera_com_backoff_e_tenta_de_novo() -> None:
    respostas = [_erro(4), _erro(17), httpx.Response(200, json={"data": []})]
    dormidos: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return respostas.pop(0)

    cliente = _cliente(handler, dormidos)
    assert cliente.get("me/accounts", {}) == {"data": []}
    assert dormidos == [10.0, 20.0]  # dobra a cada tentativa
    assert cliente.chamadas == 3


def test_limite_persistente_levanta_erro_de_limite_retomavel() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _erro(32)

    with pytest.raises(ErroLimite):
        _cliente(handler).get("me/accounts", {})


def test_uso_do_app_acima_de_95_por_cento_pausa_antes_da_proxima() -> None:
    dormidos: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": []}, headers={"x-app-usage": json.dumps({"call_count": 96})}
        )

    cliente = _cliente(handler, dormidos)
    cliente.get("me/accounts", {})
    assert dormidos == [10.0]


def test_username_malformado_nunca_vai_para_a_query() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("não deveria chamar a rede")

    with pytest.raises(ValueError, match="username"):
        _cliente(handler).business_discovery("17841", "kim){id}")


def test_validade_do_token_via_debug_token_usa_token_do_app() -> None:
    vistos: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        vistos.append(req)
        return httpx.Response(
            200, json={"data": {"is_valid": True, "expires_at": 1796601600}}  # 2026-12-07
        )

    vence = _cliente(handler).validade_token("123", "segredo-app")
    assert vence == datetime(2026, 12, 7, tzinfo=UTC)
    assert vistos[0].headers["authorization"] == "Bearer 123|segredo-app"
    assert vistos[0].url.params["input_token"] == TOKEN or "input_token" not in vistos[0].url.params
    assert "segredo-app" not in str(vistos[0].url)


def test_token_que_nunca_expira_devolve_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"is_valid": True, "expires_at": 0}})

    assert _cliente(handler).validade_token("1", "s") is None


def test_token_invalido_falha_alto() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"is_valid": False}})

    with pytest.raises(ErroMeta, match="inválido"):
        _cliente(handler).validade_token("1", "s")


@pytest.mark.parametrize(
    ("hoje", "esperado"),
    [
        (date(2026, 10, 8), None),  # 60 dias
        (date(2026, 11, 22), "15 dia"),  # exatamente 15
        (date(2026, 12, 6), "1 dia"),
        (date(2026, 12, 7), "vence hoje"),
    ],
)
def test_aviso_quando_faltam_15_dias_ou_menos(hoje: date, esperado: str | None) -> None:
    vence = datetime(2026, 12, 7, tzinfo=UTC)
    aviso = aviso_de_vencimento(vence, hoje)
    if esperado is None:
        assert aviso is None
    else:
        assert aviso is not None
        assert esperado in aviso


def test_token_vencido_falha_alto() -> None:
    with pytest.raises(ErroMeta, match="venceu"):
        aviso_de_vencimento(datetime(2026, 12, 7, tzinfo=UTC), date(2026, 12, 8))
