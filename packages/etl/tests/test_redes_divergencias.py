"""Conferência TSE × site do Missão: só relatório de divergências, nunca fonte de dado."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
from contratos import CONTRATOS
from etl.redes.divergencias import comparar, extrair_do_site


def _objeto(sq: str, instagram: str | None, seguidores: int | None = None) -> str:
    ig = "null" if instagram is None else f'"{instagram}"'
    seg = "null" if seguidores is None else str(seguidores)
    return (
        f'{{"sq":"{sq}","nome":"X","nomeUrna":"Fulano {sq}","numero":"14","uf":"SP",'
        f'"cargo":"Deputado Federal","instagram":{ig},"seguidores":{seg},"situacao":"Deferido"}}'
    )


def _html(*objetos: str) -> str:
    """Como o Next.js embute o JSON: dentro de uma string JS, com aspas escapadas."""
    corpo = ",".join(objetos).replace('"', '\\"')
    return f'<html><script>self.__next_f.push([1,"[{corpo}]"])</script></html>'


def test_extrai_sq_instagram_e_seguidores_do_payload_do_site() -> None:
    html = _html(_objeto("1", "Ana.Silva", 120), _objeto("2", None))
    site = extrair_do_site(html)
    assert site.sort("sq_candidato").rows() == [(1, "ana.silva", 120), (2, None, None)]


def _tse(*linhas: tuple[int, str, bool]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ano_eleicao": [2026] * len(linhas),
            "sq_candidato": [sq for sq, _, _ in linhas],
            "rede": ["instagram"] * len(linhas),
            "username": [u for _, u, _ in linhas],
            "url_tse": ["x"] * len(linhas),
            "nr_ordem": list(range(1, len(linhas) + 1)),
            "principal": [p for _, _, p in linhas],
            "dt_geracao": [date(2026, 10, 8)] * len(linhas),
        },
        schema=dict(CONTRATOS["redes_candidatos"].colunas),
    )


def test_classifica_cada_caso(tmp_path: Path) -> None:
    tse = _tse(
        (1, "igual", True),
        (2, "principal_tse", True),
        (2, "perfil_do_site", False),
        (3, "diferente_tse", True),
        (4, "so_tse", True),
        (8, "fora_do_site", True),
    )
    site = extrair_do_site(
        _html(
            _objeto("1", "igual", 10),
            _objeto("2", "perfil_do_site", 20),
            _objeto("3", "diferente_site", 30),
            _objeto("4", None),
            _objeto("5", "so_no_site", 50),
            _objeto("6", None),
        )
    )
    nomes = pl.DataFrame({"sq_candidato": [1, 2, 3, 4, 5, 6, 7, 8]})
    rel = comparar(tse, site, nomes.with_columns(nm_urna_candidato=pl.lit("N"), sg_uf=pl.lit("SP")))
    por_sq = {r["sq_candidato"]: r for r in rel.iter_rows(named=True)}
    assert 1 not in por_sq  # iguais não entram no relatório
    assert por_sq[2]["divergencia"] == "site_usa_perfil_alternativo_do_tse"
    assert por_sq[3]["divergencia"] == "perfis_diferentes"
    assert por_sq[4]["divergencia"] == "so_no_tse"
    assert por_sq[5]["divergencia"] == "so_no_site"
    assert por_sq[8]["divergencia"] == "candidato_ausente_no_site"
    assert 6 not in por_sq  # nenhum dos dois tem Instagram: nada a conferir
    assert por_sq[3]["instagram_site"] == "diferente_site"
    assert por_sq[3]["instagram_tse"] == "diferente_tse"
    assert por_sq[2]["instagram_tse_alternativos"] == "perfil_do_site"
