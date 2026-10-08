"""Contratos das redes sociais: cadastro do TSE e coleta no Instagram (ADR 0008).

``redes_candidatos`` vem do TSE (``rede_social_candidato_AAAA``): uma linha por
candidatura × perfil distinto (o candidato pode declarar conta pessoal, de campanha e do
partido), com o ``username`` já normalizado; ``principal`` marca o declarado primeiro. ``redes_perfis`` é uma **série de
snapshots** (um registro por coleta — nunca se sobrescreve, é assim que nasce o histórico de
seguidores, que a API não fornece). ``redes_posts`` guarda a última leitura de cada post.
Contagens ocultas pelo dono (curtidas) ficam **nulas**, nunca zero.
"""

from __future__ import annotations

import polars as pl

from contratos.modelo import Contrato

STATUS_PERFIL = ("ok", "nao_comercial", "nao_encontrado")
_UTC = pl.Datetime("us", "UTC")

REDES_CANDIDATOS = Contrato(
    nome="redes_candidatos",
    colunas={
        "ano_eleicao": pl.Int16, "sq_candidato": pl.Int64, "rede": pl.Utf8,
        "username": pl.Utf8, "url_tse": pl.Utf8, "nr_ordem": pl.Int32, "principal": pl.Boolean,
        "dt_geracao": pl.Date,
    },
    chave=("ano_eleicao", "sq_candidato", "rede", "username"),
    nao_nulas=(
        "ano_eleicao", "sq_candidato", "rede", "username", "url_tse", "nr_ordem", "principal",
    ),
    derivadas=frozenset({"rede", "username", "principal"}),
)  # fmt: skip

REDES_PERFIS = Contrato(
    nome="redes_perfis",
    colunas={
        "sq_candidato": pl.Int64, "ano_eleicao": pl.Int16, "rede": pl.Utf8,
        "username": pl.Utf8, "status": pl.Utf8, "followers_count": pl.Int64,
        "follows_count": pl.Int64, "media_count": pl.Int64, "coletado_em": _UTC,
    },
    chave=("sq_candidato", "ano_eleicao", "rede", "coletado_em"),
    nao_nulas=("sq_candidato", "ano_eleicao", "rede", "username", "status", "coletado_em"),
    faixas={
        "followers_count": (0, 10**10), "follows_count": (0, 10**10), "media_count": (0, 10**8),
    },
)  # fmt: skip

REDES_POSTS = Contrato(
    nome="redes_posts",
    colunas={
        "username": pl.Utf8, "media_id": pl.Utf8, "timestamp": _UTC, "media_type": pl.Utf8,
        "media_product_type": pl.Utf8, "like_count": pl.Int64, "comments_count": pl.Int64,
        "permalink": pl.Utf8, "coletado_em": _UTC,
    },
    chave=("username", "media_id"),
    nao_nulas=("username", "media_id", "timestamp", "media_type", "coletado_em"),
    faixas={"like_count": (0, 10**10), "comments_count": (0, 10**10)},
)  # fmt: skip

CONTRATOS_REDES = {c.nome: c for c in (REDES_CANDIDATOS, REDES_PERFIS, REDES_POSTS)}
