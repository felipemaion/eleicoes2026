"""Parser de username do Instagram sobre os formatos reais do cadastro do TSE (2026)."""

from __future__ import annotations

import pytest
from etl.redes.url import username_instagram


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("HTTPS://WWW.INSTAGRAM.COM/MIGUEL_BOMJARDIM/", "miguel_bomjardim"),
        ("HTTPS://WWW.INSTAGRAM.COM/LENILDALUNA", "lenildaluna"),
        ("HTTPS://WWW.INSTAGRAM.COM/TIAGO.SIMIONI?IGSH=MXDZMXRQBTM4BTN1NQ%3D%3D", "tiago.simioni"),
        ("HTTPS://WWW.INSTAGRAM.COM/CRIADOAERORANCHO?UTM_SOURCE=QR&IGSH=OGJS", "criadoaerorancho"),
        ("HTTPS://WWW.INSTAGRAM.COM/ATHAALLY/?HL=PT-BR", "athaally"),
        ("HTTPS://WWW.INSTAGRAM.COM/PAULOLEMOSAP/#", "paulolemosap"),
        ("HTTPS://INSTAGRAM.COM/LILIANFERREIRARAMOS?", "lilianferreiraramos"),
        ("INSTAGRAM.COM/MIRIAMMELCHIORIOFICIAL", "miriammelchiorioficial"),
        ("WWW.INSTAGRAM.COM/PROFLUCIENECAVALCANTE/", "proflucienecavalcante"),
        ("https://www.instagram.com/@claudiacoutinhoof", "claudiacoutinhoof"),
        ("https://www.instagram.com/sarah?igsh=cXhjaHZuMjF 0bmFi", "sarah"),
        ("https://www.instagram.com/_u/kimkataguiri", "kimkataguiri"),
        ("@VALERIOBELTRAO", "valeriobeltrao"),
        ("INSTAGRAM: @BATATAANDERSON11", "batataanderson11"),
        ("INSTAGRAM: GAMBA_GEOVANE", "gamba_geovane"),
        ("@DEPZESILVA - INSTAGRAM", "depzesilva"),
        ("INSTAGRAM @OTAVIOXERIFE", "otavioxerife"),
        ("@MARLUCEALVESDEASSIS9 INSTAGRAM", "marlucealvesdeassis9"),
        ("INSTAGRAM - @SABRINALEONEL.ES", "sabrinaleonel.es"),
        ("LINEUOLIMPIO - INSTAGRAM", "lineuolimpio"),
        ("Instagram jairo.cardoso.1447", "jairo.cardoso.1447"),
        ("INSTAGRAM: HTTPS://WWW.INSTAGRAM.COM/EMANUELPINHEIRONETO/", "emanuelpinheironeto"),
        ("INSTAGRAM:https://@vivianepalestrante", "vivianepalestrante"),
        ("JUNIAAMAS (INSTAGRAM)", "juniaamas"),
        ("INSTAGRAM/ JANICE.P.LEAL", "janice.p.leal"),
        ("INSTAGRAM.COM@EDUARDORODRIGUES.LUTA", "eduardorodrigues.luta"),
        ("HTTPS://INSTAGRAM@PROF.MARCIOLADEIRA", "prof.marcioladeira"),
        ("WWW.INSTAGRAN/@DRCAIOGRACCO", "drcaiogracco"),
        ("@VAGGNERGASTTAO/INSTAGRAM", "vaggnergasttao"),
    ],
)
def test_extrai_username(texto: str, esperado: str) -> None:
    assert username_instagram(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "https://www.instagram.com/channel/AbaB0WMm9Ahi1rgt/",  # canal, não perfil
        "https://www.instagram.com/p/Dct19DbuamP/?igsi=MnppNzJ4bGQ0eG9r",  # post
        "HTTPS://WWW.INSTAGRAM.COM/P/DIC3UF_O8MY/?IGSH=MXNREJLMANJ1DJG4ZA==",
        "https://www.instagram.com/reel/Cx1/",
        "HTTPS://WWW.INSTAGRAM.COM/UID/549742922",  # id numérico, não username
        "https://www.instagram.com/stories/fulano/123/",
        "https://www.instagram.com/explore/tags/eleicoes/",
        "INSTAGRAM: SAULO SPEROTTO",  # nome, não handle (espaço)
        "@ADVOGADAFLAVIAPRAZERES (TIKTOK)",  # outra rede
        "HTTPS://WWW.TIKTOK.COM/@FALCAOMINAS",
        "https://www.facebook.com/eduardowartchowNovo",
        "https://x.com/MateusWesp",
        "https://www.instagram.com/",
        "INSTAGRAM",
        "",
        "   ",
        "https://www.instagram.com/" + "a" * 31,  # > 30 caracteres
        "https://joaquimroriz.com.br/",
    ],
)
def test_rejeita_o_que_nao_e_perfil(texto: str) -> None:
    assert username_instagram(texto) is None


def test_ponto_final_de_frase_e_descartado() -> None:
    # "@fulano." no fim de uma frase: o ponto é pontuação, não parte do handle
    assert username_instagram("@fulano.") == "fulano"
