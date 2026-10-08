"""Coleta incremental de perfis e posts do Instagram (Business Discovery) — ADR 0008.

Fluxo por ``username`` (candidatos que compartilham o perfil gastam uma só consulta):

1. página 1 traz o perfil (seguidores etc.) → **um snapshot por coleta** em ``redes_perfis``;
2. pagina as mídias (mais novas primeiro) até cobrir ``desde`` ou alcançar um post já
   conhecido — o primeiro dia lê tudo desde 01/01/2026, os seguintes costumam gastar 1 chamada;
3. cada resposta é guardada em ``data/raw/meta/<dia>/<username>/<cursor>.json``: reexecutar no
   mesmo dia (após limite ou queda) não repete chamadas e não duplica linhas.

Erro de token/permissão e limite persistente interrompem a rodada, mas o que já foi coletado
é gravado antes (``finally``). Nada aqui lê ou grava o token.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from contratos import CONTRATOS, validar

from etl.redes.meta import VERSAO_API, ClienteMeta, Pagina, PerfilIndisponivel

DESDE_PADRAO = date(2026, 1, 1)
# Conta pessoal/inexistente raramente muda: relê a cada 7 dias em vez de gastar 1 chamada/dia.
REVERIFICAR_INDISPONIVEL = timedelta(days=7)
CT_PERFIS = CONTRATOS["redes_perfis"]
CT_POSTS = CONTRATOS["redes_posts"]


@dataclass(frozen=True)
class _Resposta:
    """Uma consulta (da rede ou do cache): a página ou o status que a explica."""

    coletado_em: datetime
    pagina: Pagina | None
    status: str  # "ok" | "nao_comercial" | "nao_encontrado"


def _para_json(r: _Resposta) -> dict[str, Any]:
    pagina = None
    if r.pagina is not None:
        pagina = {
            **{k: v for k, v in vars(r.pagina).items() if k != "midias"},
            "midias": [{**m, "timestamp": m["timestamp"].isoformat()} for m in r.pagina.midias],
        }
    return {"coletado_em": r.coletado_em.isoformat(), "status": r.status, "pagina": pagina}


def _de_json(bruto: dict[str, Any]) -> _Resposta:
    pagina = None
    if bruto["pagina"] is not None:
        p = bruto["pagina"]
        midias = [{**m, "timestamp": datetime.fromisoformat(m["timestamp"])} for m in p["midias"]]
        pagina = Pagina(**{**p, "midias": midias})
    return _Resposta(datetime.fromisoformat(bruto["coletado_em"]), pagina, bruto["status"])


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


def _consultar(
    cliente: ClienteMeta,
    conta_id: str,
    username: str,
    cursor: str | None,
    cache: Path,
    agora: Callable[[], datetime],
) -> _Resposta:
    """Lê do cache do dia ou consulta a API e guarda a resposta."""
    nome = hashlib.sha256((cursor or "").encode()).hexdigest()[:16] if cursor else "inicio"
    arquivo = cache / username / f"{nome}.json"
    if arquivo.exists():
        return _de_json(json.loads(arquivo.read_text(encoding="utf-8")))
    quando = agora()
    try:
        resposta = _Resposta(quando, cliente.business_discovery(conta_id, username, cursor), "ok")
    except PerfilIndisponivel as e:
        resposta = _Resposta(quando, None, e.status)
    _escrever(arquivo, json.dumps(_para_json(resposta), ensure_ascii=False))
    return resposta


def _percorrer(
    cliente: ClienteMeta,
    conta_id: str,
    username: str,
    *,
    cache: Path,
    agora: Callable[[], datetime],
    corte: datetime,
    conhecido: datetime | None,
) -> tuple[_Resposta, list[dict[str, Any]]]:
    """Primeira resposta (perfil) e as mídias a gravar, da mais nova até o corte/já conhecido."""
    primeira = _consultar(cliente, conta_id, username, None, cache, agora)
    midias: list[dict[str, Any]] = []
    resposta = primeira
    while resposta.pagina is not None:
        pagina = resposta.pagina
        midias += [dict(m, coletado_em=resposta.coletado_em) for m in pagina.midias]
        datas = [m["timestamp"] for m in pagina.midias]
        chegou_no_antigo = any(d < corte for d in datas)
        chegou_no_conhecido = conhecido is not None and any(d <= conhecido for d in datas)
        if pagina.proximo is None or chegou_no_antigo or chegou_no_conhecido or not datas:
            break
        resposta = _consultar(cliente, conta_id, username, pagina.proximo, cache, agora)
    return primeira, [m for m in midias if m["timestamp"] >= corte]


def _recem_indisponivel(perfis: pl.DataFrame, username: str, agora: datetime) -> bool:
    """Último snapshot não-ok e recente: não vale gastar chamada (ver REVERIFICAR_INDISPONIVEL)."""
    ultimo = perfis.filter(pl.col("username") == username).sort("coletado_em").tail(1)
    if ultimo.is_empty():
        return False
    linha = ultimo.row(0, named=True)
    return bool(linha["status"] != "ok" and agora - linha["coletado_em"] < REVERIFICAR_INDISPONIVEL)


def _ler_ou_vazio(caminho: Path, contrato_nome: str) -> pl.DataFrame:
    if caminho.exists():
        return pl.read_parquet(caminho)
    return pl.DataFrame(schema=dict(CONTRATOS[contrato_nome].colunas))


def _gravar(
    saida: Path,
    perfis: pl.DataFrame,
    posts: pl.DataFrame,
) -> None:
    """Valida contra os contratos e troca os Parquets de forma atômica."""
    validar(perfis, CT_PERFIS)
    validar(posts, CT_POSTS)
    saida.mkdir(parents=True, exist_ok=True)
    for nome, df in (("redes_perfis", perfis), ("redes_posts", posts)):
        tmp = saida / f"{nome}.parquet.tmp"
        df.write_parquet(tmp)
        os.replace(tmp, saida / f"{nome}.parquet")


def coletar(
    cliente: ClienteMeta,
    conta_id: str,
    candidatos: pl.DataFrame,
    *,
    raiz_raw: Path,
    raiz_processed: Path,
    agora: Callable[[], datetime],
    desde: date = DESDE_PADRAO,
    limite: int | None = None,
) -> dict[str, Any]:
    """Coleta os perfis de ``candidatos`` (``redes_candidatos``) e acumula em ``redes/``.

    ``limite`` corta a rodada em N usernames (medição de custo, retomada em lotes). Os perfis
    principais vêm primeiro: uma rodada interrompida cobre antes o que mais importa.
    """
    inicio = agora()
    chamadas0 = cliente.chamadas
    saida = raiz_processed / "redes"
    perfis = _ler_ou_vazio(saida / "redes_perfis.parquet", "redes_perfis")
    posts = _ler_ou_vazio(saida / "redes_posts.parquet", "redes_posts")
    posts_antes = posts.height
    ordenados = candidatos.sort(["principal", "sq_candidato"], descending=[True, False])
    usernames = [
        u
        for u in ordenados["username"].unique(maintain_order=True).to_list()
        if not _recem_indisponivel(perfis, u, inicio)
    ][:limite]
    cache = raiz_raw / "meta" / inicio.date().isoformat()
    corte = datetime.combine(desde, time.min, tzinfo=UTC)
    novos_perfis: list[dict[str, Any]] = []
    novos_posts: list[dict[str, Any]] = []
    por_status: Counter[str] = Counter()
    posts_final = posts

    def consolidar() -> tuple[pl.DataFrame, pl.DataFrame]:
        p = pl.concat([perfis, pl.DataFrame(novos_perfis, schema=dict(CT_PERFIS.colunas))]).unique(
            subset=list(CT_PERFIS.chave), keep="last"
        )
        q = pl.concat([posts, pl.DataFrame(novos_posts, schema=dict(CT_POSTS.colunas))]).unique(
            subset=list(CT_POSTS.chave), keep="last"
        )
        return p.sort("coletado_em", "sq_candidato", "username"), q.sort("username", "timestamp")

    try:
        for username in usernames:
            conhecido = posts.filter(pl.col("username") == username)["timestamp"].max()
            primeira, midias = _percorrer(
                cliente,
                conta_id,
                username,
                cache=cache,
                agora=agora,
                corte=corte,
                conhecido=conhecido,  # type: ignore[arg-type]
            )
            por_status[primeira.status] += 1
            p = primeira.pagina
            for c in ordenados.filter(pl.col("username") == username).iter_rows(named=True):
                novos_perfis.append(
                    {
                        "sq_candidato": c["sq_candidato"],
                        "ano_eleicao": c["ano_eleicao"],
                        "rede": c["rede"],
                        "username": username,
                        "status": primeira.status,
                        "followers_count": p.seguidores if p else None,
                        "follows_count": p.seguindo if p else None,
                        "media_count": p.midias_total if p else None,
                        "coletado_em": primeira.coletado_em,
                    }
                )
            novos_posts += [{"username": username, **m} for m in midias]
    finally:
        if novos_perfis:
            perfis_final, posts_final = consolidar()
            _gravar(saida, perfis_final, posts_final)
            _anexar_manifesto(
                saida / "manifesto.json",
                {
                    "iniciada_em": inicio.isoformat(),
                    "finalizada_em": agora().isoformat(),
                    "versao_api": VERSAO_API,
                    "desde": desde.isoformat(),
                    "chamadas": cliente.chamadas - chamadas0,
                    "perfis": dict(sorted(por_status.items())),
                },
            )
    return {
        "perfis": dict(sorted(por_status.items())),
        "usernames": len(usernames),
        "posts_novos": posts_final.height - posts_antes,
        "chamadas": cliente.chamadas - chamadas0,
    }


def _anexar_manifesto(caminho: Path, coleta: dict[str, Any]) -> None:
    atual = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {"coletas": []}
    atual["coletas"].append(coleta)
    _escrever(caminho, json.dumps(atual, indent=2, ensure_ascii=False) + "\n")
