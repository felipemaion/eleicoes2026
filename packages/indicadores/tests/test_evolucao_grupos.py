"""Bordas de `indicadores.evolucao` e `indicadores.grupos`."""

import polars as pl
import pytest
from indicadores import desempenho, evolucao, financeiro, grupos

AMC = pl.DataFrame({"cd_mun_ibge": [1, 2], "amc": [1, 2]})


def _ano(votos: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {"cd_mun_ibge": [1, 2], "aptos": [100, 200], "validos": [80, 150], "votos": votos}
    )


def test_municipio_fora_da_tabela_amc_falha() -> None:
    amc = pl.DataFrame({"cd_mun_ibge": [1], "amc": [1]})
    with pytest.raises(ValueError, match="sem AMC"):
        evolucao.evolucao(_ano([1, 2]), _ano([1, 2]), amc)


def test_unidade_so_num_ano_fica_nula() -> None:
    a26 = _ano([5, 5]).filter(pl.col("cd_mun_ibge") == 1)
    df = evolucao.evolucao(_ano([1, 2]), a26, AMC).sort("amc")
    assert df["delta_penetracao"].to_list()[1] is None


def test_evolucao_por_entidade() -> None:
    a22 = _ano([1, 2]).with_columns(pl.lit("g").alias("grupo"))
    a26 = _ano([2, 2]).with_columns(pl.lit("g").alias("grupo"))
    df = evolucao.evolucao(a22, a26, AMC, por=("grupo",)).sort("amc")
    assert df["ganho_absoluto"].to_list() == [1, 0]


def test_spearman_com_empates() -> None:
    a = pl.Series([1.0, 2.0, 2.0, 3.0])
    b = pl.Series([1.0, 2.0, 3.0, 4.0])
    assert evolucao.spearman(a, b) == pytest.approx(0.9486832981)


def test_spearman_curto_e_nulo() -> None:
    assert evolucao.spearman(pl.Series([1.0]), pl.Series([2.0])) is None


def test_mesmos_candidatos_sem_intersecao() -> None:
    a = pl.DataFrame({"pessoa_id": ["p1"], "votos": [10]})
    b = pl.DataFrame({"pessoa_id": ["p2"], "votos": [10]})
    linha = evolucao.mesmos_candidatos(a, b).row(0, named=True)
    assert linha["pessoa_ids"] == []
    assert linha["retencao"] is None


VOTOS = pl.DataFrame(
    {
        "sq_candidato": ["a", "a", "b", "z"],
        "cd_mun_ibge": [1, 2, 1, 1],
        "cd_cargo": [6, 6, 6, 6],
        "votos": [10, 5, 7, 100],
    }
)


def test_agregar_grupo_soma_membros() -> None:
    df = grupos.agregar_grupo(VOTOS, ["a", "b", "ausente"], "missao_2026").sort("cd_mun_ibge")
    assert df.columns == ["grupo", "cd_mun_ibge", "votos"]
    assert df["votos"].to_list() == [17, 5]
    assert df["grupo"].unique().to_list() == ["missao_2026"]


def test_grupo_alimenta_indicadores_como_candidato_coletivo() -> None:
    municipios = pl.DataFrame({"cd_mun_ibge": [1, 2], "aptos": [1000, 500], "validos": [800, 400]})
    df = grupos.agregar_grupo(VOTOS, ["a", "b"], "g")
    tab = desempenho.indicadores_municipais(df, municipios, entidade="grupo")
    uf = desempenho.totais_uf(tab, entidade="grupo").row(0, named=True)
    assert uf["votos"] == 22
    assert uf["penetracao"] == pytest.approx(1000 * 22 / 1500)


def test_agregar_grupo_recusa_cargos_misturados() -> None:
    df = VOTOS.with_columns(pl.Series("cd_cargo", [6, 7, 6, 6]))
    with pytest.raises(ValueError, match="um cargo por vez"):
        grupos.agregar_grupo(df, ["a", "b"], "g")


def test_agregar_grupo_recusa_turnos_misturados() -> None:
    df = VOTOS.with_columns(pl.Series("nr_turno", [1, 2, 1, 1]))
    with pytest.raises(ValueError, match="um turno por vez"):
        grupos.agregar_grupo(df, ["a", "b"], "g")


def test_agregar_grupo_sem_membros_falha() -> None:
    with pytest.raises(ValueError, match="sem membros"):
        grupos.agregar_grupo(VOTOS, [], "g")


def test_n_candidatos_conta_so_aptos() -> None:
    cand = pl.DataFrame(
        {
            "sq_candidato": ["a", "b", "c", "z"],
            "sg_uf": ["SP", "SP", "RJ", "SP"],
            "ds_situacao_candidatura": ["APTO", "INAPTO", "APTO", "APTO"],
        }
    )
    total = grupos.n_candidatos(cand, ["a", "b", "c"])
    assert total["n_candidatos"].item() == 2
    por_uf = grupos.n_candidatos(cand, ["a", "b", "c"], por=("sg_uf",)).sort("sg_uf")
    assert por_uf.to_dicts() == [
        {"sg_uf": "RJ", "n_candidatos": 1},
        {"sg_uf": "SP", "n_candidatos": 1},
    ]


def test_receitas_do_grupo_excluem_transferencia_interna() -> None:
    receitas = pl.DataFrame(
        {
            "sq_candidato": ["a", "b", "b"],
            "ds_fonte_receita": ["Fundo Especial", "Outros Recursos", "Outros Recursos"],
            "ds_origem_receita": [
                "Recursos de partido político",
                "Recursos de outros candidatos",
                "Recursos de outros candidatos",
            ],
            "ds_natureza_receita": ["Financeiro", "Financeiro", "Financeiro"],
            "sq_candidato_doador": [None, "a", "x"],
            "vr_receita": [100.0, 30.0, 20.0],
        },
        schema_overrides={"sq_candidato_doador": pl.String},
    )
    linha = grupos.receitas_grupo(financeiro.classificar_receitas(receitas), ["a", "b"]).row(
        0, named=True
    )
    assert linha["receita_total"] == 120.0
    assert linha["receita_outros_candidatos"] == 20.0
