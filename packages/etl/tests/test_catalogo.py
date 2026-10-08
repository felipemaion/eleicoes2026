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
    assert len(alvos(2026, ["votacao_secao"])) == len(UFS)
    assert "BR" in UFS  # presidente: arquivo próprio, não vem nos arquivos por UF


def test_votacao_secao_2022_nao_tem_zz() -> None:
    """O TSE não publica `votacao_secao_2022_ZZ.zip` (404): exterior vem no arquivo BR."""
    ufs_2022 = {a.destino.split("_")[-1].removesuffix(".zip") for a in alvos(2022, ["votacao_secao"])}
    assert "ZZ" not in ufs_2022
    assert ufs_2022 == set(UFS) - {"ZZ"}
    [a] = alvos(2026, ["votacao_secao"], uf="ZZ")
    assert a.url.endswith("votacao_secao_2026_ZZ.zip")
    assert alvos(2022, ["votacao_secao"], uf="ZZ") == []


def test_fontes_sem_ano() -> None:
    [m] = alvos(2026, ["municipio_tse_ibge"])
    assert m.url == f"{BASE}/municipio_tse_ibge/municipio_tse_ibge.zip"
    [i] = alvos(2026, ["ipca"])
    assert "sgs.433" in i.url
    [g] = alvos(2026, ["malha_municipios"])
    assert g.url.endswith("municipio_2025/Brasil/BR_Municipios_2025.zip")


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


def test_areas_e_malha_ufs_no_catalogo() -> None:
    [a] = alvos(2026, ["areas_ibge"])
    assert a.url.endswith("AR_BR_RG_UF_RGINT_RGI_MUN_2025.xls")
    [u] = alvos(2026, ["malha_ufs"])
    assert "paises/BR" in u.url
    assert "intrarregiao=UF" in u.url
