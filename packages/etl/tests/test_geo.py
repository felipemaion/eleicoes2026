"""Camadas geográficas (municípios, UFs, zonas) e empacotamento PMTiles."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import polars as pl
import pytest
import shapefile  # type: ignore[import-untyped]
from etl.geo import (
    ErroGeo,
    camada_municipios,
    camada_zonas,
    escrever_geojsonseq,
    gerar_pmtiles,
    ler_malha,
)
from shapely.geometry import Polygon, box, mapping
from shapely.geometry.base import BaseGeometry

pytestmark_tiles = pytest.mark.skipif(
    shutil.which("tippecanoe") is None or shutil.which("pmtiles") is None,
    reason="tippecanoe/pmtiles ausentes",
)


def _zip_shapefile(destino: Path, itens: list[tuple[str, BaseGeometry]]) -> Path:
    """Shapefile mínimo (CD_MUN, NM_MUN) dentro de um ZIP, como o do IBGE."""
    base = destino.parent / "BR_Municipios_2025"
    with shapefile.Writer(str(base), shapeType=shapefile.POLYGON) as w:
        w.field("CD_MUN", "C", 7)
        w.field("NM_MUN", "C", 40)
        for cod, geom in itens:
            w.record(cod, "x")
            w.poly([list(geom.exterior.coords)])  # type: ignore[attr-defined]
    with zipfile.ZipFile(destino, "w") as z:
        for ext in ("shp", "shx", "dbf"):
            z.write(f"{base}.{ext}", f"BR_Municipios_2025.{ext}")
    return destino


def test_ler_malha_le_shapefile_zipado_e_converte_codigo(tmp_path: Path) -> None:
    zp = _zip_shapefile(tmp_path / "m.zip", [("1200138", box(0, 0, 1, 1))])
    [(cod, geom)] = ler_malha(zp)
    assert cod == 1200138
    assert geom.area == pytest.approx(1.0)


def test_ler_malha_simplifica_com_a_tolerancia_pedida(tmp_path: Path) -> None:
    ruidoso = Polygon([(0, 0), (0.5, 0.0001), (1, 0), (1, 1), (0, 1)])
    zp = _zip_shapefile(tmp_path / "m.zip", [("1", ruidoso)])
    [(_, bruta)] = ler_malha(zp, tolerancia=0)
    [(_, simples)] = ler_malha(zp, tolerancia=0.001)
    assert len(simples.exterior.coords) < len(bruta.exterior.coords)  # type: ignore[attr-defined]


def test_camada_municipios_traz_nome_e_exige_todos() -> None:
    mun = pl.DataFrame(
        {"cd_mun_ibge": [1, 2], "nm_municipio": ["A", "B"], "cd_amc": [10, 10]},
        schema_overrides={"cd_mun_ibge": pl.Int32, "cd_amc": pl.Int32},
    )
    malha = [(1, box(0, 0, 1, 1)), (2, box(1, 0, 2, 1))]
    feats = camada_municipios(malha, mun)
    assert [f["properties"] for f in feats] == [
        {"cd_mun_ibge": 1, "nome": "A", "cd_amc": 10},
        {"cd_mun_ibge": 2, "nome": "B", "cd_amc": 10},
    ]
    with pytest.raises(ErroGeo, match="2"):
        camada_municipios(malha[:1], mun)


def _locais() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "cd_mun_ibge": [1, 1, 1, None],
            "nr_zona": [1, 2, 2, 5],
            "nr_latitude": [0.5, 0.5, 0.5, 0.5],
            "nr_longitude": [0.2, 1.8, 1.9, 0.5],
            "qt_eleitor_secao": [10, 10, 10, 10],
        },
        schema_overrides={"cd_mun_ibge": pl.Int32, "nr_zona": pl.Int16},
    )


def test_camada_zonas_id_e_relatorio() -> None:
    poligonos = {1: box(0, 0, 2, 1)}
    feats, rel = camada_zonas(_locais(), poligonos, {1: "Alfa"})
    ids = sorted(f["properties"]["id"] for f in feats)
    assert ids == ["1-1", "1-2"]
    assert all(set(f["properties"]) == {"cd_mun_ibge", "nr_zona", "id", "nome"} for f in feats)
    assert {f["properties"]["nome"] for f in feats} == {"Alfa — zona 1", "Alfa — zona 2"}
    assert rel.locais_sem_municipio == 1  # exterior (cd_mun_ibge nulo)
    assert rel.zonas_sem_poligono == []


def test_camada_zonas_relata_municipio_sem_poligono() -> None:
    with pytest.raises(ErroGeo, match="sem polígono"):
        camada_zonas(_locais(), {})


@pytestmark_tiles
def test_gerar_pmtiles_nome_com_hash_e_manifesto(tmp_path: Path) -> None:
    arq = tmp_path / "a.geojsonl"
    escrever_geojsonseq(
        arq,
        [
            {
                "type": "Feature",
                "properties": {"id": "x"},
                "geometry": mapping(box(-50, -10, -49, -9)),
            }
        ],
    )
    saida = tmp_path / "tiles"
    pm = gerar_pmtiles(
        {"municipios": arq}, saida, ids={"municipios": "cd_mun_ibge"}, zoom_min=3, zoom_max=6
    )
    assert pm.name.startswith("municipios.")
    assert pm.suffix == ".pmtiles"
    man = json.loads((saida / "manifesto.json").read_text())
    assert man["arquivo"] == pm.name
    assert man["camadas"] == {
        "municipios": {
            "arquivo": pm.name,
            "camada": "municipios",
            "id": "cd_mun_ibge",
            "limites": [-50, -10, -49, -9],
        }
    }
    assert len(pm.name.split(".")[1]) == 12
    show = subprocess.run(  # noqa: S603
        [shutil.which("pmtiles") or "pmtiles", "show", str(pm)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "municipios" in show.stdout
    # idempotente: mesma entrada, mesmo nome; sobras antigas removidas
    pm2 = gerar_pmtiles(
        {"municipios": arq}, saida, ids={"municipios": "cd_mun_ibge"}, zoom_min=3, zoom_max=6
    )
    assert pm2.name == pm.name
    assert len(list(saida.glob("*.pmtiles"))) == 1
