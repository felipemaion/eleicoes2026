"""Conferência dos perfis do TSE com o site candidatos.missao.org.br (só relatório).

O site é de terceiros (o partido): **não** alimenta nenhum dado publicado. O HTML do Next.js
embute a lista de candidatos como JSON dentro de uma string JS; extraímos só ``sq``,
``instagram`` e ``seguidores`` e listamos onde o cadastro oficial e o site discordam.
Sem CPF: o relatório usa o ``sq_candidato`` público.
"""

from __future__ import annotations

import re

import httpx
import polars as pl

URL_SITE = "https://candidatos.missao.org.br"
# `"sq":"123"` seguido (no mesmo objeto) de `"instagram":"x"|null` e, opcional, `"seguidores"`
_OBJETO = re.compile(
    r'"sq":"(?P<sq>\d+)"(?:(?!"sq":").)*?"instagram":(?:"(?P<ig>[^"]*)"|null)'
    r'(?:,"seguidores":(?P<seg>\d+|null))?',
    re.DOTALL,
)


def baixar_site(url: str = URL_SITE) -> str:
    """HTML da página inicial (a lista inteira vem embutida; ~3 MB)."""
    resposta = httpx.get(url, timeout=60.0, follow_redirects=True)
    resposta.raise_for_status()
    return resposta.text


def extrair_do_site(html: str) -> pl.DataFrame:
    """``sq_candidato``, ``instagram`` (minúsculo, sem ``@``) e ``seguidores`` do site."""
    texto = html.replace('\\\\"', '"').replace('\\"', '"')
    linhas: dict[int, tuple[int, str | None, int | None]] = {}
    for m in _OBJETO.finditer(texto):
        ig = m.group("ig")
        seg = m.group("seg")
        sq = int(m.group("sq"))
        linhas[sq] = (
            sq,
            ig.strip().lstrip("@").lower() if ig else None,
            int(seg) if seg and seg != "null" else None,
        )
    return pl.DataFrame(
        list(linhas.values()),
        schema={"sq_candidato": pl.Int64, "instagram": pl.Utf8, "seguidores": pl.Int64},
        orient="row",
    )


def comparar(tse: pl.DataFrame, site: pl.DataFrame, nomes: pl.DataFrame) -> pl.DataFrame:
    """Linhas onde o TSE (``redes_candidatos``) e o site discordam, com a classificação.

    ``nomes`` traz ``sq_candidato``, ``nm_urna_candidato`` e ``sg_uf`` (de ``consulta_cand``).
    Quem tem o mesmo perfil nos dois, ou em nenhum, não aparece.
    """
    principal = tse.filter(pl.col("principal")).select(
        "sq_candidato", pl.col("username").alias("instagram_tse")
    )
    alternativos = (
        tse.filter(~pl.col("principal"))
        .group_by("sq_candidato")
        .agg(pl.col("username").sort().str.join(",").alias("instagram_tse_alternativos"))
    )
    base = (
        site.rename({"instagram": "instagram_site", "seguidores": "seguidores_site"})
        .join(principal, on="sq_candidato", how="full", coalesce=True)
        .join(alternativos, on="sq_candidato", how="left")
        .join(nomes, on="sq_candidato", how="left")
    )
    tem_site, tem_tse = (
        pl.col("instagram_site").is_not_null(),
        pl.col("instagram_tse").is_not_null(),
    )
    alternativos_lista = pl.col("instagram_tse_alternativos").fill_null("").str.split(",")
    divergencia = (
        pl.when(tem_site & ~tem_tse)
        .then(pl.lit("so_no_site"))
        .when(~tem_site & tem_tse & ~pl.col("sq_candidato").is_in(site["sq_candidato"].implode()))
        .then(pl.lit("candidato_ausente_no_site"))
        .when(~tem_site & tem_tse)
        .then(pl.lit("so_no_tse"))
        .when(tem_site & tem_tse & (pl.col("instagram_site") == pl.col("instagram_tse")))
        .then(pl.lit("igual"))
        .when(tem_site & tem_tse & alternativos_lista.list.contains(pl.col("instagram_site")))
        .then(pl.lit("site_usa_perfil_alternativo_do_tse"))
        .when(tem_site & tem_tse)
        .then(pl.lit("perfis_diferentes"))
        .otherwise(pl.lit("nenhum"))
    )
    return (
        base.with_columns(divergencia.alias("divergencia"))
        .filter(~pl.col("divergencia").is_in(["igual", "nenhum"]))
        .select(
            "sq_candidato",
            "nm_urna_candidato",
            "sg_uf",
            "divergencia",
            "instagram_tse",
            "instagram_tse_alternativos",
            "instagram_site",
            "seguidores_site",
        )
        .sort("divergencia", "sg_uf", "sq_candidato")
    )
