"""Bordas e erros de `indicadores.financeiro` não cobertos pelos vetores."""

import polars as pl
import pytest
from indicadores import financeiro


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
