"""Bordas e erros de `indicadores.financeiro` não cobertos pelos vetores."""

import json
from pathlib import Path

import polars as pl
import pytest
from indicadores import financeiro, grupos


def _receita(fonte: str, origem: str, natureza: str = "Financeiro") -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sq_candidato": ["c1"],
            "ds_fonte_receita": [fonte],
            "ds_origem_receita": [origem],
            "ds_natureza_receita": [natureza],
            "vr_receita": [10.0],
        }
    )


def test_classificacao_ignora_caixa_e_acento() -> None:
    df = financeiro.classificar_receitas(
        _receita("Fundo Partidário", "Recursos de Partido Político")
    )
    assert df["categoria"].to_list() == ["fundo_partidario"]


def test_partido_com_outros_recursos() -> None:
    df = financeiro.classificar_receitas(
        _receita("Outros Recursos", "Recursos de partido político")
    )
    assert df["categoria"].to_list() == ["partido_outros_recursos"]


def test_origem_desconhecida_falha() -> None:
    with pytest.raises(ValueError, match="ds_origem_receita desconhecida"):
        financeiro.classificar_receitas(_receita("Outros Recursos", "Recursos do além"))


def test_natureza_desconhecida_falha() -> None:
    with pytest.raises(ValueError, match="ds_natureza_receita desconhecida"):
        financeiro.resumo_receitas(
            financeiro.classificar_receitas(
                _receita("Outros Recursos", "Recursos próprios", "Bitcoin")
            )
        )


def test_resumo_por_candidato() -> None:
    df = pl.concat(
        [
            _receita("FUNDO ESPECIAL", "Recursos de partido político"),
            _receita("OUTROS RECURSOS", "Recursos próprios", "Estimado"),
        ]
    )
    linha = financeiro.resumo_receitas(financeiro.classificar_receitas(df)).row(0, named=True)
    assert linha["sq_candidato"] == "c1"
    assert linha["receita_total"] == 20.0
    assert linha["receita_financeira"] == 10.0
    assert linha["pct_publico"] == 50.0
    assert linha["pct_autofinanciamento"] == 50.0


def test_despesa_paga_por_prestador() -> None:
    df = pl.DataFrame(
        {
            "sq_prestador_contas": [7, 7],
            "ds_origem_despesa": [
                "Publicidade",
                "Doações financeiras a outros candidatos/partidos",
            ],
            "vr_pagto_despesa": [100.0, 50.0],
        }
    )
    res = financeiro.despesa_campanha(df, "vr_pagto_despesa", por=("sq_prestador_contas",))
    assert res.to_dicts() == [{"sq_prestador_contas": 7, "despesa": 100.0}]


def test_custo_agregado_exclui_sem_contas_e_sem_votos() -> None:
    df = pl.DataFrame(
        {
            "sq_candidato": ["a", "b", "c"],
            "despesa_contratada": [100.0, None, 10.0],
            "despesa_paga": [50.0, None, 10.0],
            "votos": [10, 5, 0],
        }
    )
    linha = financeiro.custo_por_voto_agregado(df).row(0, named=True)
    assert linha["custo_voto_contratado"] == 10.0
    assert linha["candidatos_sem_voto_excluidos"] == 1
    assert linha["candidatos_sem_contas_excluidos"] == 1
    assert linha["mediana_custo_voto_contratado"] == 10.0


def test_custo_agregado_vazio_e_nulo() -> None:
    df = pl.DataFrame(
        {"sq_candidato": ["a"], "despesa_contratada": [1.0], "despesa_paga": [1.0], "votos": [0]}
    )
    linha = financeiro.custo_por_voto_agregado(df).row(0, named=True)
    assert linha["custo_voto_contratado"] is None
    assert linha["custo_voto_pago"] is None


SERIE = financeiro.serie_ipca({"2022-10": 0.59, "2022-11": 0.41, "2022-12": 0.62})


def test_mes_base_usa_alvo_quando_publicado() -> None:
    assert financeiro.resolver_mes_base(SERIE, "2022-09", "2022-11") == "2022-11"


def test_mes_base_cai_no_ultimo_disponivel_emenda_adr_0007() -> None:
    assert financeiro.resolver_mes_base(SERIE, "2022-09", "2026-09") == "2022-12"


def test_mes_base_sem_meses_apos_origem_falha() -> None:
    with pytest.raises(ValueError, match="origem"):
        financeiro.resolver_mes_base(SERIE, "2022-12", "2026-09")


def test_mes_base_antes_da_origem_falha() -> None:
    with pytest.raises(ValueError, match="anterior"):
        financeiro.fator_ipca(SERIE, "2022-12", "2022-10")


def test_mes_mal_formado_falha() -> None:
    with pytest.raises(ValueError, match="AAAA-MM"):
        financeiro.fator_ipca(SERIE, "set/2022", "2022-12")


def test_virada_de_ano() -> None:
    serie = financeiro.serie_ipca({"2022-12": 1.0, "2023-01": 1.0})
    assert financeiro.fator_ipca(serie, "2022-11", "2023-01") == pytest.approx(1.0201)


def test_custo_sem_pagamento_lancado_conta_pago_como_zero() -> None:
    # Prestador com despesa contratada e nenhuma linha em despesas_pagas: pagou 0, não "sem dado".
    df = pl.DataFrame(
        {"despesa_contratada": [1000.0, None], "despesa_paga": [None, None], "votos": [100, 50]}
    )
    linhas = financeiro.custo_por_voto(df).to_dicts()
    assert linhas[0]["custo_voto_pago"] == 0.0
    assert linhas[0]["divida"] == 1000.0
    # Sem contas (contratada nula) continua indefinido.
    assert linhas[1]["custo_voto_pago"] is None
    assert linhas[1]["divida"] is None


_ROTULOS_REAIS = json.loads(
    (Path(__file__).parent / "fixtures" / "rotulos_receita_2022_2026.json").read_text("utf-8")
)["combinacoes"]


def _tabela_real() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "sq_candidato": f"{c['ano']}-{i}",
                "ds_fonte_receita": c["ds_fonte_receita"],
                "ds_origem_receita": c["ds_origem_receita"],
                "ds_natureza_receita": c["ds_natureza_receita"],
                "vr_receita": 1.0,
                "esperada": c["categoria_esperada"],
            }
            for i, c in enumerate(_ROTULOS_REAIS)
        ]
    )


def test_rotulos_reais_2022_2026_classificados_conforme_spec() -> None:
    df = financeiro.classificar_receitas(_tabela_real())
    divergentes = df.filter(pl.col("categoria") != pl.col("esperada"))
    assert divergentes.is_empty(), divergentes
    assert {c["ano"] for c in _ROTULOS_REAIS} == {2022, 2026}


def test_rotulos_reais_naturezas_aceitas_no_resumo() -> None:
    resumo = financeiro.resumo_receitas(financeiro.classificar_receitas(_tabela_real()), por=())
    estimaveis = sum(1 for c in _ROTULOS_REAIS if c["ds_natureza_receita"] != "FINANCEIRO")
    assert resumo["receita_total"][0] == len(_ROTULOS_REAIS)
    assert resumo["receita_financeira"][0] == len(_ROTULOS_REAIS) - estimaveis


@pytest.mark.parametrize(
    ("origem", "categoria"),
    [
        ("Fundo Especial de Financiamento de Campanha", "fefc"),
        ("Fundo Partidário", "fundo_partidario"),
        ("Doações para Campanha", "outros_candidatos"),
    ],
)
def test_origens_2026_de_repasse_entre_candidatos(origem: str, categoria: str) -> None:
    df = financeiro.classificar_receitas(_receita("OUTROS RECURSOS", origem))
    assert df["categoria"].to_list() == [categoria]


def test_fonte_nula_falha() -> None:
    df = _receita("x", "Recursos próprios").with_columns(
        pl.lit(None, pl.String).alias("ds_fonte_receita")
    )
    with pytest.raises(ValueError, match="ds_fonte_receita desconhecida"):
        financeiro.classificar_receitas(df)


# --- T-A08: indicadores de receita (spec §4.4–4.10) ---


def test_despesa_com_transferencias_para_o_saldo() -> None:
    df = pl.DataFrame(
        {
            "sq_candidato": [1, 1],
            "ds_origem_despesa": [
                "Publicidade",
                "Doações financeiras a outros candidatos/partidos",
            ],
            "vr_despesa_contratada": [100.0, 50.0],
        }
    )
    res = financeiro.despesa_campanha(df, "vr_despesa_contratada", incluir_transferencias=True)
    assert res.to_dicts() == [{"sq_candidato": 1, "despesa": 150.0}]


def test_resumo_por_candidato_traz_composicao_e_concentracao() -> None:
    df = financeiro.classificar_receitas(
        pl.DataFrame(
            {
                "sq_candidato": [1, 1, 2],
                "ds_fonte_receita": ["FUNDO ESPECIAL", "OUTROS RECURSOS", "OUTROS RECURSOS"],
                "ds_origem_receita": [
                    "Recursos de outros candidatos",
                    "Recursos de pessoas físicas",
                    "Recursos próprios",
                ],
                "ds_natureza_receita": ["FINANCEIRO", "ESTIMÁVEL", "FINANCEIRO"],
                "vr_receita": [30.0, 10.0, 5.0],
            }
        )
    )
    linhas = financeiro.resumo_receitas(df).to_dicts()
    assert linhas[0]["receita_repasses_candidatos"] == 30.0
    assert linhas[0]["receita_sem_repasses"] == 10.0
    assert linhas[0]["pct_estimavel"] == 25.0
    assert linhas[0]["hhi_fontes"] == 0.75**2 + 0.25**2
    assert linhas[1]["n_efetivo_fontes"] == 1.0


def test_receitas_grupo_aceita_doador_inteiro_nulo() -> None:
    """Como a API entrega hoje: coluna presente, toda nula → repasse vira "doador desconhecido"."""
    df = financeiro.classificar_receitas(
        pl.DataFrame(
            {
                "sq_candidato": [1, 2],
                "ds_fonte_receita": ["FUNDO ESPECIAL", "OUTROS RECURSOS"],
                "ds_origem_receita": ["Recursos de outros candidatos", "Recursos próprios"],
                "ds_natureza_receita": ["FINANCEIRO", "FINANCEIRO"],
                "vr_receita": [30.0, 5.0],
                "sq_candidato_doador": [None, None],
            },
            schema_overrides={"sq_candidato_doador": pl.Int64},
        )
    )
    linha = grupos.receitas_grupo(df, [1, 2]).row(0, named=True)
    assert linha["receita_total"] == 35.0
    assert linha["receita_repasses_internos"] == 0.0
    assert linha["receita_repasses_doador_desconhecido"] == 30.0


def test_receita_por_mil_aptos_coluna_ausente_falha() -> None:
    with pytest.raises(ValueError, match="colunas ausentes"):
        financeiro.receita_por_mil_aptos(pl.DataFrame({"receita_total": [1.0]}))


def test_receita_por_voto_agregado_sem_elegiveis_e_nulo() -> None:
    df = pl.DataFrame(
        {"receita_total": [None, 10.0], "votos": [5, 0]},
        schema={"receita_total": pl.Float64, "votos": pl.Int64},
    )
    linha = financeiro.receita_por_voto_agregado(df).row(0, named=True)
    assert linha["receita_por_voto"] is None
    assert linha["mediana_receita_por_voto"] is None
    assert linha["candidatos_sem_voto_excluidos"] == 1
    assert linha["candidatos_sem_contas_excluidos"] == 1


def test_comparar_receitas_coluna_em_duas_listas_falha() -> None:
    serie = financeiro.serie_ipca({"2022-10": 1.0})
    df = pl.DataFrame({"x_2022": [1.0], "x_2026": [2.0]})
    with pytest.raises(ValueError, match="monetária e percentual"):
        financeiro.comparar_receitas(df, ["x"], ["x"], serie, "2022-09", "2022-10")


def test_comparar_receitas_nao_altera_entrada_nem_corrige_percentual() -> None:
    serie = financeiro.serie_ipca({"2022-10": 10.0})
    df = pl.DataFrame(
        {"r_2022": [100.0], "r_2026": [110.0], "pct_x_2022": [5.0], "pct_x_2026": [7.0]}
    )
    res = financeiro.comparar_receitas(df, ["r"], ["pct_x"], serie, "2022-09", "2022-10")
    linha = res.row(0, named=True)
    assert abs(linha["r_2022"] - 110.0) < 1e-9
    assert abs(linha["delta_r"]) < 1e-9
    assert linha["pct_x_2022"] == 5.0
    assert linha["delta_pct_x"] == 2.0
    assert "var_pct_pct_x" not in res.columns
    assert df["r_2022"].item() == 100.0
