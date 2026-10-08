"""Zonas eleitorais aproximadas: Voronoi dos locais de votação recortado pelo município.

Não há polígono oficial de zona (ADR 0003). A célula de cada local é atribuída à zona dele;
a zona é a união das suas células. O Voronoi é planar em graus: distorção desprezível na
escala de um município e fronteira entre zonas é só uma aproximação.
"""

from __future__ import annotations

from dataclasses import dataclass

import shapely
from shapely.geometry import MultiPoint, Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep


@dataclass(frozen=True)
class Local:
    """Local de votação com coordenada; ``eleitores`` desempata coordenadas repetidas."""

    nr_zona: int
    lon: float
    lat: float
    eleitores: int = 0


def zonas_do_municipio(municipio: BaseGeometry, locais: list[Local]) -> dict[int, BaseGeometry]:
    """``nr_zona → polígono`` dentro de ``municipio``.

    Zona única recebe o próprio município. Locais fora do município são descartados
    (coordenada inválida do TSE) e coordenadas repetidas ficam com a zona de mais eleitores;
    zona sem nenhum local válido não ganha polígono — o chamador relata, sem inventar área.
    """
    dentro = prep(municipio)
    validos = [loc for loc in locais if dentro.covers(Point(loc.lon, loc.lat))]
    # coordenada repetida: um só ponto semente, da zona com mais eleitores
    por_ponto: dict[tuple[float, float], Local] = {}
    for loc in validos:
        chave = (loc.lon, loc.lat)
        if chave not in por_ponto or loc.eleitores > por_ponto[chave].eleitores:
            por_ponto[chave] = loc
    sementes = list(por_ponto.values())
    zonas = {loc.nr_zona for loc in locais}
    if len(zonas) == 1:
        return {next(iter(zonas)): municipio}
    if not sementes:
        return {}
    if len(sementes) == 1:
        return {sementes[0].nr_zona: municipio}

    celulas = shapely.voronoi_polygons(
        MultiPoint([(s.lon, s.lat) for s in sementes]), extend_to=municipio.envelope.buffer(1.0)
    )
    por_zona: dict[int, list[BaseGeometry]] = {}
    for celula in celulas.geoms:
        dono = next(s for s in sementes if celula.covers(Point(s.lon, s.lat)))
        por_zona.setdefault(dono.nr_zona, []).append(celula.intersection(municipio))
    return {z: shapely.union_all(cs) for z, cs in por_zona.items()}
