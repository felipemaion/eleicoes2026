"""Camadas geográficas e empacotamento em PMTiles (tippecanoe)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import shapefile  # type: ignore[import-untyped]  # pyshp sem stubs
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from etl.zonas import Local, zonas_do_municipio

Feature = dict[str, Any]


class ErroGeo(ValueError):  # noqa: N818 - nome de domínio
    """Geometria faltando ou inconsistente."""


@dataclass
class RelatorioZonas:
    """O que ficou de fora da camada de zonas (nada é inventado nem escondido)."""

    locais_sem_municipio: int = 0
    zonas_sem_poligono: list[str] = field(default_factory=list)


def ler_malha(caminho: Path, *, tolerancia: float = 0.0005) -> list[tuple[int, BaseGeometry]]:
    """Shapefile (ZIP) da Malha Municipal do IBGE → ``(CD_MUN inteiro, geometria)``.

    ``tolerancia`` (graus; 0,0005 ≈ 50 m) simplifica preservando topologia: o shapefile
    tem resolução cadastral, mais do que o zoom 10 do mapa precisa.
    """
    saida: list[tuple[int, BaseGeometry]] = []
    with shapefile.Reader(str(caminho)) as leitor:
        campos = [c[0] for c in leitor.fields[1:]]
        for sr in leitor.iterShapeRecords():
            geom = shape(sr.shape.__geo_interface__)
            if tolerancia:
                geom = geom.simplify(tolerancia, preserve_topology=True)
            saida.append((int(dict(zip(campos, sr.record, strict=True))["CD_MUN"]), geom))
    return saida


def camada_municipios(
    malha: list[tuple[int, BaseGeometry]], municipios: pl.DataFrame
) -> list[Feature]:
    """Features com ``cd_mun_ibge`` (int) e ``nm``; falha se algum município não tiver geometria."""
    por_cod = dict(malha)
    faltam = sorted(set(municipios["cd_mun_ibge"].to_list()) - set(por_cod))
    if faltam:
        raise ErroGeo(f"município(s) sem geometria na malha: {faltam[:10]} ({len(faltam)})")
    return [
        {
            "type": "Feature",
            "properties": {"cd_mun_ibge": cod, "nm": nm},
            "geometry": mapping(por_cod[cod]),
        }
        for cod, nm in municipios.sort("cd_mun_ibge")
        .select("cd_mun_ibge", "nm_municipio")
        .iter_rows()
    ]


def camada_zonas(
    locais: pl.DataFrame, poligonos: dict[int, BaseGeometry]
) -> tuple[list[Feature], RelatorioZonas]:
    """Voronoi por município a partir de ``locais`` (colunas de eleitorado_local_votacao)."""
    rel = RelatorioZonas()
    rel.locais_sem_municipio = locais.filter(pl.col("cd_mun_ibge").is_null()).height
    com_mun = locais.filter(pl.col("cd_mun_ibge").is_not_null())
    sem_poligono = sorted(set(com_mun["cd_mun_ibge"].to_list()) - set(poligonos))
    if sem_poligono:
        raise ErroGeo(f"município(s) com locais mas sem polígono: {sem_poligono[:10]}")
    feats: list[Feature] = []
    for chave, grupo in com_mun.group_by("cd_mun_ibge", maintain_order=True):
        cod = int(str(chave[0]))
        itens = [
            Local(z, lon, lat, eleit or 0)
            for z, lat, lon, eleit in grupo.select(
                "nr_zona", "nr_latitude", "nr_longitude", "qt_eleitor_secao"
            ).iter_rows()
            if lat is not None and lon is not None
        ]
        declaradas = set(grupo["nr_zona"].to_list())
        zonas = zonas_do_municipio(poligonos[cod], itens)
        rel.zonas_sem_poligono += [f"{cod}-{z}" for z in sorted(declaradas - set(zonas))]
        for z, geom in sorted(zonas.items()):
            if geom.is_empty:
                rel.zonas_sem_poligono.append(f"{cod}-{z}")
                continue
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"cd_mun_ibge": cod, "nr_zona": z, "id": f"{cod}-{z}"},
                    "geometry": mapping(geom),
                }
            )
    return feats, rel


def escrever_geojsonseq(caminho: Path, features: list[Feature]) -> None:
    """Uma feature por linha (formato que o tippecanoe lê em streaming)."""
    caminho.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in features) + "\n")


def gerar_pmtiles(
    camadas: dict[str, Path], saida: Path, *, zoom_min: int = 3, zoom_max: int = 10
) -> Path:
    """GeoJSONSeq por camada → ``municipios.<hash12>.pmtiles`` + ``manifesto.json``.

    O hash é do conteúdo do PMTiles: URL nova a cada mudança, cache eterno no Caddy.
    """
    if shutil.which("tippecanoe") is None:
        raise ErroGeo("tippecanoe não instalado (brew install tippecanoe)")
    saida.mkdir(parents=True, exist_ok=True)
    tmp = saida / "_build.pmtiles"
    cmd = ["tippecanoe", "-o", str(tmp), "--force", "-Z", str(zoom_min), "-z", str(zoom_max),
           "--detect-shared-borders", "--drop-densest-as-needed", "--no-progress-indicator",
           "--read-parallel"]  # fmt: skip
    for nome, arq in camadas.items():
        cmd += ["-L", json.dumps({"file": str(arq), "layer": nome})]
    r = subprocess.run(  # noqa: S603 - argumentos montados aqui, sem shell
        cmd, capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise ErroGeo(f"tippecanoe falhou: {r.stderr[-500:]}")
    sha = hashlib.sha256()
    with tmp.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            sha.update(bloco)
    final = saida / f"municipios.{sha.hexdigest()[:12]}.pmtiles"
    tmp.replace(final)
    for velho in saida.glob("municipios.*.pmtiles"):
        if velho != final:
            velho.unlink()
    (saida / "manifesto.json").write_text(
        json.dumps(
            {
                "arquivo": final.name,
                "sha256": sha.hexdigest(),
                "bytes": final.stat().st_size,
                "camadas": list(camadas),
                "zoom": [zoom_min, zoom_max],
                "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n"
    )
    return final
