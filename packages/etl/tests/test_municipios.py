"""Tabela de municípios: áreas IBGE, crosswalk TSE↔IBGE e AMC."""

import polars as pl
import pytest
from contratos import CONTRATOS, ContratoViolado, validar
from etl.municipios import (
    AGREGACOES_AMC,
    ErroMunicipios,
    calcular_amc,
    limpar_areas,
    montar_municipios,
)

SORRISO, NOVA_UBIRATA, BOA_ESPERANCA = 5107925, 5106240, 5101837


def crosswalk() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sg_uf": ["MT", "MT", "MT", "AC"],
            "cd_municipio_tse": [98930, 90000, 73709, 1007],
            "nm_municipio_ibge": ["Sorriso", "Nova Ubiratã", "Boa Esperança do Norte", "Bujari"],
            "cd_mun_ibge": [SORRISO, NOVA_UBIRATA, BOA_ESPERANCA, 1200138],
        },
        schema_overrides={"cd_municipio_tse": pl.Int32, "cd_mun_ibge": pl.Int32},
    )


def areas_brutas() -> pl.DataFrame:
    """Como sai do .xls do IBGE: códigos em texto, lagoas e rodapé junto."""
    return pl.DataFrame(
        {
            "CD_MUN": ["4300001", "5107925", "5106240", "5101837", "1200138", None],
            "NM_MUN": ['Área Operacional "Lagoa Mirim"', "Sorriso", "x", "y", "z", "OBS: ..."],
            "AR_MUN_2025": [2884.3, 9330.1, 12000.0, 800.5, 3000.2, None],
        }
    )


def test_limpar_areas_descarta_lagoas_e_rodape() -> None:
    a = limpar_areas(areas_brutas())
    assert sorted(a["cd_mun_ibge"].to_list()) == [1200138, 5101837, 5106240, 5107925]
    assert a.schema == {"cd_mun_ibge": pl.Int32, "area_km2": pl.Float64}


def test_amc_agrega_boa_esperanca_do_norte_a_origem() -> None:
    amc = calcular_amc([SORRISO, NOVA_UBIRATA, BOA_ESPERANCA, 1200138])
    # os três (nova + as duas de origem) compartilham a AMC; o resto é a própria
    assert len({amc[SORRISO], amc[NOVA_UBIRATA], amc[BOA_ESPERANCA]}) == 1
    assert amc[1200138] == 1200138
    assert amc[SORRISO] == min(SORRISO, NOVA_UBIRATA, BOA_ESPERANCA)


def test_agregacoes_documentadas_tem_fonte() -> None:
    for ag in AGREGACOES_AMC:
        assert ag.fonte.startswith("http")
        assert ag.nova not in ag.origens


def test_amc_exige_municipio_conhecido() -> None:
    with pytest.raises(ErroMunicipios, match="9999999"):
        calcular_amc([SORRISO], agregacoes=[_ag(9999999)])


def _ag(nova: int):  # type: ignore[no-untyped-def]
    from etl.municipios import AgregacaoAmc

    return AgregacaoAmc(nova=nova, origens=(SORRISO,), fonte="https://exemplo")


def test_montar_municipios_respeita_o_contrato() -> None:
    m = montar_municipios(crosswalk(), limpar_areas(areas_brutas()))
    validar(m, CONTRATOS["municipios"])
    linha = m.filter(pl.col("cd_mun_ibge") == BOA_ESPERANCA).row(0, named=True)
    assert linha["cd_mun_tse"] == 73709
    assert linha["nm_municipio"] == "Boa Esperança do Norte"
    assert linha["area_km2"] == pytest.approx(800.5)
    assert linha["cd_amc"] == min(SORRISO, NOVA_UBIRATA, BOA_ESPERANCA)


def test_montar_municipios_falha_alto_sem_area() -> None:
    areas = limpar_areas(areas_brutas()).filter(pl.col("cd_mun_ibge") != 1200138)
    with pytest.raises(ErroMunicipios, match="1200138"):
        montar_municipios(crosswalk(), areas)


def test_contrato_recusa_area_negativa() -> None:
    m = montar_municipios(crosswalk(), limpar_areas(areas_brutas())).with_columns(
        area_km2=pl.lit(-1.0)
    )
    with pytest.raises(ContratoViolado):
        validar(m, CONTRATOS["municipios"])
