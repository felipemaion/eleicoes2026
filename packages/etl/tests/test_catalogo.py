import pytest
from etl.fontes.catalogo import UFS, alvos

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele"


@pytest.mark.parametrize("ano", [2022, 2026])
def test_urls_tse_por_ano(ano: int) -> None:
    [a] = alvos(ano, ["votacao_candidato_munzona"])
    assert a.url == f"{BASE}/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip"
    [b] = alvos(ano, ["prestacao_contas"])
    assert b.url.endswith(f"/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip")


def test_votacao_secao_uma_uf() -> None:
    [a] = alvos(2026, ["votacao_secao"], uf="SP")
    assert a.url == f"{BASE}/votacao_secao/votacao_secao_2026_SP.zip"
    assert a.destino == "tse/votacao_secao/votacao_secao_2026_SP.zip"


def test_votacao_secao_todas_as_ufs() -> None:
    assert len(alvos(2022, ["votacao_secao"])) == len(UFS)


def test_fontes_sem_ano() -> None:
    [m] = alvos(2026, ["municipio_tse_ibge"])
    assert m.url == f"{BASE}/municipio_tse_ibge/municipio_tse_ibge.zip"
    [i] = alvos(2026, ["ipca"])
    assert "sgs.433" in i.url
    [g] = alvos(2026, ["malha_ibge"], uf="SP")
    assert "estados/SP?" in g.url


def test_destinos_unicos() -> None:
    destinos = [a.destino for a in alvos(2026)]
    assert len(destinos) == len(set(destinos))


@pytest.mark.parametrize(
    ("args", "msg"),
    [
        ((2020, None, None), "ano"),
        ((2026, ["x"], None), "desconhecida"),
        ((2026, None, "XX"), "UF"),
    ],
)
def test_entradas_invalidas(args: tuple[int, list[str] | None, str | None], msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        alvos(*args)
