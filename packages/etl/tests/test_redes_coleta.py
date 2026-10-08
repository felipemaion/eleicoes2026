"""Coleta de perfis e posts: paginação, incremental, status e retomada — rede simulada."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import polars as pl
import pytest
from contratos import CONTRATOS, validar
from etl.redes.coleta import coletar
from etl.redes.meta import ClienteMeta, ErroMeta

TAM_PAGINA = 2  # a API real devolve até 50; páginas pequenas exercitam o cursor
DESDE = date(2026, 1, 1)


def _post(i: int, dia: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"m{i}",
        "timestamp": f"{dia}T12:00:00+0000",
        "media_type": "IMAGE",
        "media_product_type": "FEED",
        "like_count": 10 * i,
        "comments_count": i,
        "permalink": f"https://www.instagram.com/p/m{i}/",
        **extra,
    }


class Grafo:
    """Graph API simulada: perfis comerciais com posts (mais novo primeiro) e erros por perfil."""

    def __init__(self) -> None:
        self.perfis: dict[str, dict[str, Any]] = {}
        self.erros: dict[str, httpx.Response] = {}
        self.pedidos: list[httpx.Request] = []

    def adicionar(self, username: str, posts: list[dict[str, Any]], seguidores: int = 100) -> None:
        self.perfis[username] = {"followers": seguidores, "posts": posts}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.pedidos.append(req)
        if req.url.path.endswith("/me/accounts"):
            return httpx.Response(200, json={"data": [{"instagram_business_account": {"id": "IG"}}]})
        campos = req.url.params["fields"]
        username = re.search(r"username\(([^)]+)\)", campos)
        assert username
        nome = username.group(1)
        if nome in self.erros:
            return self.erros[nome]
        if nome not in self.perfis:
            return httpx.Response(400, json={"error": {"code": 110, "error_subcode": 2207013}})
        cursor = re.search(r"after\(([^)]+)\)", campos)
        inicio = int(cursor.group(1)) if cursor else 0
        perfil = self.perfis[nome]
        fatia = perfil["posts"][inicio : inicio + TAM_PAGINA]
        media: dict[str, Any] = {"data": fatia}
        if inicio + TAM_PAGINA < len(perfil["posts"]):
            media["paging"] = {
                "cursors": {"after": str(inicio + TAM_PAGINA)},
                "next": "https://graph.facebook.com/...",
            }
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "username": nome,
                    "followers_count": perfil["followers"],
                    "follows_count": 7,
                    "media_count": len(perfil["posts"]),
                    "media": media,
                }
            },
        )

    def chamadas_de(self, username: str) -> int:
        return sum(f"username({username})" in r.url.params.get("fields", "") for r in self.pedidos)


@pytest.fixture
def grafo() -> Grafo:
    g = Grafo()
    g.adicionar(
        "ana",
        [
            _post(5, "2026-10-05"),
            _post(4, "2026-09-01", like_count=None),  # curtidas ocultas
            _post(3, "2026-03-10"),
            _post(2, "2026-01-02"),
            _post(1, "2025-12-31"),  # antes de 2026-01-01: fora da janela
            _post(0, "2025-06-01"),
        ],
        seguidores=1000,
    )
    g.adicionar("bia", [_post(9, "2026-10-01")], seguidores=50)
    return g


def _candidatos(*linhas: tuple[int, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ano_eleicao": [2026] * len(linhas),
            "sq_candidato": [sq for sq, _ in linhas],
            "rede": ["instagram"] * len(linhas),
            "username": [u for _, u in linhas],
            "url_tse": [f"https://instagram.com/{u}" for _, u in linhas],
            "nr_ordem": [1] * len(linhas),
            "principal": [True] * len(linhas),
            "dt_geracao": [date(2026, 10, 8)] * len(linhas),
        },
        schema=dict(CONTRATOS["redes_candidatos"].colunas),
    )


def _rodar(
    grafo: Grafo,
    tmp: Path,
    candidatos: pl.DataFrame,
    quando: datetime,
    **kw: Any,
) -> dict[str, Any]:
    cliente = ClienteMeta(
        "tok", http=httpx.Client(transport=httpx.MockTransport(grafo)), dormir=lambda _: None
    )
    return coletar(
        cliente,
        "IG",
        candidatos,
        raiz_raw=tmp / "raw",
        raiz_processed=tmp / "proc",
        agora=lambda: quando,
        desde=DESDE,
        **kw,
    )


def _ler(tmp: Path, nome: str) -> pl.DataFrame:
    return pl.read_parquet(tmp / "proc/redes" / f"{nome}.parquet")


DIA1 = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
DIA2 = DIA1 + timedelta(days=1)


def test_primeira_coleta_pagina_ate_o_corte_e_grava_perfil_e_posts(
    grafo: Grafo, tmp_path: Path
) -> None:
    stats = _rodar(grafo, tmp_path, _candidatos((1, "ana"), (2, "bia")), DIA1)
    perfis, posts = _ler(tmp_path, "redes_perfis"), _ler(tmp_path, "redes_posts")
    validar(perfis, CONTRATOS["redes_perfis"])
    validar(posts, CONTRATOS["redes_posts"])
    ana = perfis.filter(pl.col("username") == "ana").row(0, named=True)
    assert (ana["status"], ana["followers_count"], ana["follows_count"]) == ("ok", 1000, 7)
    assert ana["media_count"] == 6
    assert ana["coletado_em"] == DIA1
    # 2026-only: m1 (31/12/2025) e m0 ficam de fora; a paginação precisou de 3 chamadas
    assert sorted(posts.filter(pl.col("username") == "ana")["media_id"]) == ["m2", "m3", "m4", "m5"]
    assert grafo.chamadas_de("ana") == 3
    assert stats["perfis"] == {"ok": 2}
    assert stats["posts_novos"] == 5


def test_curtida_oculta_fica_nula_no_parquet(grafo: Grafo, tmp_path: Path) -> None:
    _rodar(grafo, tmp_path, _candidatos((1, "ana")), DIA1)
    posts = _ler(tmp_path, "redes_posts")
    assert posts.filter(pl.col("media_id") == "m4")["like_count"].to_list() == [None]
    assert posts.filter(pl.col("media_id") == "m5")["like_count"].to_list() == [50]


def test_segundo_dia_e_incremental_e_acumula_snapshot(grafo: Grafo, tmp_path: Path) -> None:
    cand = _candidatos((1, "ana"))
    _rodar(grafo, tmp_path, cand, DIA1)
    grafo.pedidos.clear()
    grafo.perfis["ana"]["followers"] = 1100
    grafo.perfis["ana"]["posts"].insert(0, _post(6, "2026-10-08"))
    stats = _rodar(grafo, tmp_path, cand, DIA2)
    # a 1ª página (m6, m5) já tem um post conhecido: não precisa paginar além dela
    assert grafo.chamadas_de("ana") == 1
    assert stats["posts_novos"] == 1
    perfis = _ler(tmp_path, "redes_perfis").sort("coletado_em")
    assert perfis["followers_count"].to_list() == [1000, 1100]  # série de snapshots
    assert _ler(tmp_path, "redes_posts").height == 5


def test_post_conhecido_tem_metricas_atualizadas(grafo: Grafo, tmp_path: Path) -> None:
    cand = _candidatos((1, "ana"))
    _rodar(grafo, tmp_path, cand, DIA1)
    grafo.perfis["ana"]["posts"][0]["like_count"] = 999
    _rodar(grafo, tmp_path, cand, DIA2)
    posts = _ler(tmp_path, "redes_posts")
    m5 = posts.filter(pl.col("media_id") == "m5").row(0, named=True)
    assert (m5["like_count"], m5["coletado_em"]) == (999, DIA2)
    assert posts.height == 4  # sem duplicar


def test_repetir_no_mesmo_dia_usa_o_cache_e_nao_duplica(grafo: Grafo, tmp_path: Path) -> None:
    cand = _candidatos((1, "ana"), (2, "bia"))
    _rodar(grafo, tmp_path, cand, DIA1)
    antes = len(grafo.pedidos)
    stats = _rodar(grafo, tmp_path, cand, DIA1 + timedelta(hours=2))
    assert len(grafo.pedidos) == antes  # zero chamadas: tudo veio do cache em disco
    assert stats["chamadas"] == 0
    assert _ler(tmp_path, "redes_perfis").height == 2
    assert _ler(tmp_path, "redes_posts").height == 5


def test_perfil_inexistente_vira_status_e_a_coleta_continua(grafo: Grafo, tmp_path: Path) -> None:
    stats = _rodar(grafo, tmp_path, _candidatos((1, "fantasma"), (2, "bia")), DIA1)
    perfis = _ler(tmp_path, "redes_perfis").sort("username")
    fantasma = perfis.filter(pl.col("username") == "fantasma").row(0, named=True)
    assert fantasma["status"] == "nao_encontrado"
    assert fantasma["followers_count"] is None
    assert perfis.filter(pl.col("username") == "bia")["status"].to_list() == ["ok"]
    assert stats["perfis"] == {"nao_encontrado": 1, "ok": 1}


def test_mesmo_username_de_dois_candidatos_gasta_uma_consulta(grafo: Grafo, tmp_path: Path) -> None:
    _rodar(grafo, tmp_path, _candidatos((1, "bia"), (2, "bia")), DIA1)
    assert grafo.chamadas_de("bia") == 1
    perfis = _ler(tmp_path, "redes_perfis")
    assert sorted(perfis["sq_candidato"]) == [1, 2]
    assert _ler(tmp_path, "redes_posts").height == 1  # o post é do username, não do candidato


def test_erro_de_token_falha_alto_mas_preserva_o_que_ja_foi_coletado(
    grafo: Grafo, tmp_path: Path
) -> None:
    grafo.erros["bia"] = httpx.Response(400, json={"error": {"code": 190, "message": "expirou"}})
    with pytest.raises(ErroMeta, match="190"):
        _rodar(grafo, tmp_path, _candidatos((1, "ana"), (2, "bia")), DIA1)
    assert _ler(tmp_path, "redes_perfis")["username"].to_list() == ["ana"]


def test_limite_de_perfis_por_rodada(grafo: Grafo, tmp_path: Path) -> None:
    stats = _rodar(grafo, tmp_path, _candidatos((1, "ana"), (2, "bia")), DIA1, limite=1)
    assert stats["perfis"] == {"ok": 1}
    assert _ler(tmp_path, "redes_perfis")["username"].to_list() == ["ana"]


def test_manifesto_registra_versao_da_api_horario_e_nunca_o_token(
    grafo: Grafo, tmp_path: Path
) -> None:
    _rodar(grafo, tmp_path, _candidatos((1, "ana")), DIA1)
    bruto = (tmp_path / "proc/redes/manifesto.json").read_text(encoding="utf-8")
    assert "tok" not in bruto.replace("total", "")  # o token sintético é "tok"
    [coleta] = json.loads(bruto)["coletas"]
    assert coleta["versao_api"] == "v26.0"
    assert coleta["iniciada_em"] == "2026-10-08T15:00:00+00:00"
    assert coleta["perfis"] == {"ok": 1}
    assert coleta["chamadas"] == 3
