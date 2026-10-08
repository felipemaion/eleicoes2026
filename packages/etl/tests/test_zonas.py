"""Voronoi dos locais de votação recortado pelo município (ADR 0003)."""

import pytest
from etl.zonas import Local, zonas_do_municipio
from shapely.geometry import Point, box

MUN = box(0, 0, 10, 10)


def test_zona_unica_usa_o_proprio_poligono() -> None:
    z = zonas_do_municipio(MUN, [Local(1, 3.0, 3.0, 100), Local(1, 7.0, 7.0, 50)])
    assert z.keys() == {1}
    assert z[1].equals(MUN)


def test_duas_zonas_dividem_o_municipio_sem_sobra_nem_sobreposicao() -> None:
    locais = [Local(1, 2.0, 5.0, 100), Local(2, 8.0, 5.0, 100)]
    z = zonas_do_municipio(MUN, locais)
    assert z[1].area == pytest.approx(50.0)
    assert z[2].area == pytest.approx(50.0)
    assert z[1].intersection(z[2]).area == pytest.approx(0.0)
    assert z[1].union(z[2]).area == pytest.approx(MUN.area)
    assert z[1].bounds[2] == pytest.approx(5.0)  # mediatriz em x=5


def test_zona_com_varios_locais_une_as_celulas() -> None:
    locais = [Local(1, 1.0, 5.0, 10), Local(1, 9.0, 5.0, 10), Local(2, 5.0, 5.0, 10)]
    z = zonas_do_municipio(MUN, locais)
    assert z[1].area + z[2].area == pytest.approx(MUN.area)
    assert z[2].contains(Point(5, 5))


def test_local_fora_do_municipio_e_ignorado() -> None:
    locais = [Local(1, 2.0, 5.0, 10), Local(2, 8.0, 5.0, 10), Local(2, 50.0, 50.0, 10)]
    z = zonas_do_municipio(MUN, locais)
    assert z[1].area == pytest.approx(50.0)


def test_coordenada_duplicada_fica_com_a_zona_de_mais_eleitores() -> None:
    locais = [Local(1, 2.0, 5.0, 10), Local(2, 2.0, 5.0, 99), Local(1, 8.0, 5.0, 10)]
    z = zonas_do_municipio(MUN, locais)
    assert z[2].area == pytest.approx(50.0)  # o ponto em (2,5) é da zona 2
    assert z[1].area == pytest.approx(50.0)


def test_zona_sem_nenhum_local_valido_nao_ganha_poligono() -> None:
    locais = [Local(1, 2.0, 5.0, 10), Local(1, 8.0, 5.0, 10), Local(2, 99.0, 99.0, 10)]
    z = zonas_do_municipio(MUN, locais)
    assert 2 not in z  # sem inventar área; o chamador relata a falta
