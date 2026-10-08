"""``etl geo``: municipios.parquet + PMTiles (municípios, UFs, zonas por ano)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
from contratos import CONTRATOS, validar
from shapely.geometry import mapping, shape

from etl.fontes.catalogo import alvos
from etl.geo import (
    ErroGeo,
    camada_municipios,
    camada_zonas,
    escrever_geojsonseq,
    gerar_pmtiles,
    ler_malha,
)
from etl.municipios import ler_areas, montar_municipios

ANO_CROSSWALK = 2026  # o crosswalk atual vale para os dois anos (único município novo: ver AMC)
ANOS_ZONAS = (2022, 2026)


def _raw(raiz_raw: Path, fonte: str, uf: str | None = None) -> Path:
    [alvo] = alvos(2026, [fonte], uf)
    caminho = raiz_raw / alvo.destino
    if not caminho.exists():
        raise ErroGeo(f"{caminho} não existe; rode `etl baixar --fonte {fonte}` antes")
    return caminho


def construir_municipios(raiz_raw: Path, raiz_proc: Path) -> pl.DataFrame:
    """Escreve ``<raiz_proc>/municipios.parquet`` (contrato ``municipios``)."""
    cross = pl.read_parquet(
        raiz_proc / "municipio_tse_ibge" / f"ano={ANO_CROSSWALK}" / "*.parquet"
    ).select("sg_uf", "cd_municipio_tse", "nm_municipio_ibge", "cd_mun_ibge")
    mun = montar_municipios(cross, ler_areas(_raw(raiz_raw, "areas_ibge")))
    validar(mun, CONTRATOS["municipios"])
    mun.write_parquet(raiz_proc / "municipios.parquet", compression="zstd")
    return mun


def construir_geo(raiz_raw: Path, raiz_proc: Path, saida: Path) -> dict[str, object]:
    """Gera tabela, camadas e PMTiles; devolve estatísticas para o handoff."""
    mun = construir_municipios(raiz_raw, raiz_proc)
    malha = ler_malha(_raw(raiz_raw, "malha_municipios"))
    feats_mun = camada_municipios(malha, mun)
    poligonos = dict(malha)

    ufs = json.loads(_raw(raiz_raw, "malha_ufs").read_text())["features"]
    sigla = dict(
        pl.read_parquet(raiz_proc / "municipio_tse_ibge" / f"ano={ANO_CROSSWALK}" / "*.parquet")
        .select("cd_uf_ibge", "sg_uf")
        .unique()
        .iter_rows()
    )
    feats_uf = [
        {
            "type": "Feature",
            "properties": {
                "cd_uf": int(f["properties"]["codarea"]),
                "sg_uf": sigla[int(f["properties"]["codarea"])],
            },
            "geometry": mapping(shape(f["geometry"])),
        }
        for f in ufs
    ]

    trabalho = saida / "_geojsonl"
    trabalho.mkdir(parents=True, exist_ok=True)
    camadas: dict[str, Path] = {}
    for nome, feats in (("ufs", feats_uf), ("municipios", feats_mun)):
        camadas[nome] = trabalho / f"{nome}.geojsonl"
        escrever_geojsonseq(camadas[nome], feats)

    stats: dict[str, object] = {"municipios": mun.height, "ufs": len(feats_uf)}
    for ano in ANOS_ZONAS:
        locais = pl.read_parquet(
            raiz_proc / "eleitorado_local_votacao" / f"ano={ano}" / "*.parquet"
        )
        feats, rel = camada_zonas(locais, poligonos)
        camadas[f"zonas_{ano}"] = trabalho / f"zonas_{ano}.geojsonl"
        escrever_geojsonseq(camadas[f"zonas_{ano}"], feats)
        stats[f"zonas_{ano}"] = {
            "poligonos": len(feats),
            "sem_poligono": rel.zonas_sem_poligono,
            "locais_sem_municipio": rel.locais_sem_municipio,
        }
    pm = gerar_pmtiles(camadas, saida)
    stats["pmtiles"] = {"arquivo": pm.name, "bytes": pm.stat().st_size}
    return stats
