"""Bordas e erros de `indicadores.desempenho` não cobertos pelos vetores."""

import polars as pl
import pytest
from indicadores import desempenho

MUNICIPIOS = pl.DataFrame({"cd_mun_ibge": [1, 2], "aptos": [1000, 0], "validos": [800, 0]})


def test_destinacao_desconhecida_falha() -> None:
    df = pl.DataFrame(
        {
            "sq_candidato": ["c1"],
            "cd_mun_ibge": [1],
            "nm_tipo_destinacao_votos": ["Nulo técnico"],
            "qt_votos_nominais": [1],
            "qt_votos_nominais_validos": [0],
        }
    )
    with pytest.raises(ValueError, match="nm_tipo_destinacao_votos desconhecida"):
        desempenho.votos_nominais(df)


def test_coluna_ausente_falha() -> None:
    with pytest.raises(ValueError, match="colunas ausentes"):
        desempenho.votos_nominais(pl.DataFrame({"sq_candidato": ["c1"]}))


def test_candidato_sem_linha_no_municipio_recebe_zero() -> None:
    votos = pl.DataFrame({"sq_candidato": ["c1"], "cd_mun_ibge": [1], "votos": [80]})
    df = desempenho.indicadores_municipais(votos, MUNICIPIOS).sort("cd_mun_ibge")
    assert df["votos"].to_list() == [80, 0]
    assert df["penetracao"].to_list() == [80.0, None]
    assert df["pct_validos"].to_list() == [10.0, None]
    assert df["n_baixo"].to_list() == [False, True]


def test_votos_repetidos_falham() -> None:
    votos = pl.DataFrame({"sq_candidato": ["c1", "c1"], "cd_mun_ibge": [1, 1], "votos": [1, 2]})
    with pytest.raises(ValueError, match="duplicad"):
        desempenho.montar_tabela(votos, MUNICIPIOS)


def test_municipio_repetido_falha() -> None:
    votos = pl.DataFrame({"sq_candidato": ["c1"], "cd_mun_ibge": [1], "votos": [1]})
    with pytest.raises(ValueError, match="duplicad"):
        desempenho.montar_tabela(votos, pl.concat([MUNICIPIOS, MUNICIPIOS]))


def test_municipio_sem_eleitorado_falha() -> None:
    votos = pl.DataFrame({"sq_candidato": ["c1"], "cd_mun_ibge": [9], "votos": [1]})
    with pytest.raises(ValueError, match="sem eleitorado"):
        desempenho.montar_tabela(votos, MUNICIPIOS)


def test_votos_acima_dos_validos_falham() -> None:
    votos = pl.DataFrame({"sq_candidato": ["c1"], "cd_mun_ibge": [1], "votos": [801]})
    with pytest.raises(ValueError, match="maiores que os válidos"):
        desempenho.montar_tabela(votos, MUNICIPIOS)


def test_recorte_por_zona() -> None:
    eleitorado = pl.DataFrame(
        {"cd_mun_ibge": [1, 1], "nr_zona": [1, 2], "aptos": [100, 300], "validos": [80, 200]}
    )
    votos = pl.DataFrame(
        {"sq_candidato": ["c1"], "cd_mun_ibge": [1], "nr_zona": [2], "votos": [20]}
    )
    df = desempenho.indicadores_municipais(
        votos, eleitorado, unidade=("cd_mun_ibge", "nr_zona")
    ).sort("nr_zona")
    assert df["penetracao"].to_list() == [0.0, pytest.approx(66.6666666667)]
    assert df["lq"].to_list() == [0.0, pytest.approx(1.4)]


@pytest.mark.parametrize(("validos", "vagas"), [(10, 0), (-1, 3)])
def test_quociente_eleitoral_entrada_invalida(validos: int, vagas: int) -> None:
    with pytest.raises(ValueError, match="quociente eleitoral"):
        desempenho.quociente_eleitoral(validos, vagas)


def test_votacao_partido_com_qe_zero_e_nulo() -> None:
    partidos = pl.DataFrame(
        {
            "nr_partido": [14],
            "qt_votos_legenda_validos": [0],
            "qt_votos_nom_convr_leg_validos": [0],
            "votos_nominais_validos": [0],
            "qt_total_votos_validos_uf": [0],
            "vagas": [3],
        }
    )
    linha = desempenho.votacao_partido(partidos).row(0, named=True)
    assert linha["quociente_eleitoral"] == 0
    assert linha["votacao_em_qe"] is None
    assert linha["quociente_partidario"] is None


def _votacao_dois(coluna: str, valores: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sq_candidato": ["c1", "c1"],
            "cd_mun_ibge": [1, 1],
            coluna: valores,
            "nm_tipo_destinacao_votos": ["Válido", "Válido"],
            "qt_votos_nominais": [10, 20],
            "qt_votos_nominais_validos": [10, 20],
        }
    )


@pytest.mark.parametrize(("coluna", "regra"), [("nr_turno", "turno"), ("cd_cargo", "cargo")])
def test_votos_nominais_recusa_turnos_ou_cargos_misturados(coluna: str, regra: str) -> None:
    # Somar 1º e 2º turno (ou dois cargos) dupla-contaria o eleitor (spec §0, §1.3).
    with pytest.raises(ValueError, match=f"um {regra} por vez"):
        desempenho.votos_nominais(_votacao_dois(coluna, [1, 2]))


def test_votos_nominais_aceita_turno_unico_ou_turno_nas_chaves() -> None:
    assert desempenho.votos_nominais(_votacao_dois("nr_turno", [1, 1]))[
        "votos_nominais_validos"
    ].to_list() == [30]
    por_turno = desempenho.votos_nominais(
        _votacao_dois("nr_turno", [1, 2]), chaves=("sq_candidato", "cd_mun_ibge", "nr_turno")
    )
    assert por_turno["votos_nominais_validos"].to_list() == [10, 20]
