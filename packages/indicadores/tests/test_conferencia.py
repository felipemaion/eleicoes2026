"""`indicadores.conferencia`: leitura do JSON de divulgação, votável por seção e comparação.

Vetores pequenos montados à mão no formato do resultados.tse.jus.br (ele2026, arquivo `-u.json`)
e do `votacao_secao` do TSE (spec: docs/metodologia/conferencia.md §Método).
"""

from typing import Any

import polars as pl
import pytest
from indicadores import conferencia

DOC: dict[str, Any] = {
    "ele": "6259",
    "cdabr": "sp",
    "carg": [
        {
            "cd": "6",
            "agr": [
                {
                    "par": [
                        {
                            "n": "14",
                            "sg": "MISSÃO",
                            "tvtn": "130",
                            "tvtl": "7",
                            "cand": [
                                {
                                    "n": "1414",
                                    "sqcand": "1",
                                    "dvt": "Válido",
                                    "vap": "100",
                                    "st": "Eleito por QP",
                                },
                                {
                                    "n": "1400",
                                    "sqcand": "2",
                                    "dvt": "Anulado sub judice",
                                    "vap": "30",
                                    "st": "Não eleito",
                                },
                            ],
                        }
                    ]
                },
                {
                    "par": [
                        {
                            "n": "44",
                            "sg": "UNIÃO",
                            "tvtn": "50",
                            "tvtl": "3",
                            "cand": [
                                {
                                    "n": "4433",
                                    "sqcand": "3",
                                    "dvt": "Válido",
                                    "vap": "50",
                                    "st": "Suplente",
                                }
                            ],
                        }
                    ]
                },
            ],
        }
    ],
    "e": {"te": "1000", "c": "800"},
    "v": {"vv": "160", "vnom": "150", "vl": "10", "vb": "20", "tvn": "40", "vansj": "30"},
}


def test_divulgacao_totais() -> None:
    df = conferencia.divulgacao_totais(DOC)
    assert df.to_dicts() == [
        {
            "sg_uf": "SP",
            "cd_cargo": 6,
            "aptos": 1000,
            "comparecimento": 800,
            "votos_validos": 160,
            "votos_nominais_validos": 150,
            "votos_legenda": 10,
            "votos_brancos": 20,
            "votos_nulos": 40,
        }
    ]


def test_divulgacao_totais_majoritario_sem_legenda_e_nulo() -> None:
    doc = {**DOC, "v": {k: v for k, v in DOC["v"].items() if k != "vl"}}
    assert conferencia.divulgacao_totais(doc)["votos_legenda"].to_list() == [None]


def test_divulgacao_candidatos() -> None:
    df = conferencia.divulgacao_candidatos(DOC)
    assert df.columns == [
        "sg_uf",
        "cd_cargo",
        "sq_candidato",
        "nr_candidato",
        "nr_partido",
        "destinacao",
        "situacao",
        "votos",
    ]
    assert df.select("sq_candidato", "nr_partido", "destinacao", "votos").rows() == [
        (1, 14, "Válido", 100),
        (2, 14, "Anulado sub judice", 30),
        (3, 44, "Válido", 50),
    ]


def test_divulgacao_partidos() -> None:
    df = conferencia.divulgacao_partidos(DOC)
    assert df.rows() == [("SP", 6, 14, "MISSÃO", 130, 7), ("SP", 6, 44, "UNIÃO", 50, 3)]
    assert df.columns == [
        "sg_uf",
        "cd_cargo",
        "nr_partido",
        "sg_partido",
        "votos_nominais",
        "votos_legenda",
    ]


def test_divulgacao_sem_cargo_falha() -> None:
    with pytest.raises(ValueError, match="um cargo"):
        conferencia.divulgacao_totais({**DOC, "carg": []})


SECAO = pl.DataFrame(
    {
        "cd_cargo": [6, 6, 6, 6, 6, 3, 3, 7],
        "nr_votavel": [1414, 14, 95, 96, 4433, 14, 95, 90],
    }
)


def test_classificar_votavel() -> None:
    df = conferencia.classificar_votavel(SECAO)
    # Proporcional: 2 dígitos = legenda; majoritário: 2 dígitos = candidato. 95/96 sempre.
    # 90 é partido (PROS em 2022), não código especial.
    assert df["tipo_votavel"].to_list() == [
        "nominal",
        "legenda",
        "branco",
        "nulo",
        "nominal",
        "nominal",
        "branco",
        "legenda",
    ]


def test_classificar_votavel_codigo_desconhecido_falha() -> None:
    df = pl.DataFrame({"cd_cargo": [6], "nr_votavel": [97]})
    with pytest.raises(ValueError, match="nr_votavel"):
        conferencia.classificar_votavel(df)


NOSSO = pl.DataFrame({"sg_uf": ["SP", "RJ"], "aptos": [1000, 500], "votos": [10, 5]})
FONTE = pl.DataFrame({"sg_uf": ["SP", "BA"], "aptos": [1000, 70], "votos": [12, 1]})


def test_comparar() -> None:
    df = conferencia.comparar(NOSSO, FONTE, chaves=["sg_uf"])
    assert df.columns == [
        "sg_uf",
        "medida",
        "nosso",
        "fonte",
        "diferenca",
        "diferenca_pct",
        "situacao",
    ]
    linhas = {(r["sg_uf"], r["medida"]): r for r in df.to_dicts()}
    assert linhas[("SP", "aptos")]["situacao"] == "confere"
    assert linhas[("SP", "aptos")]["diferenca"] == 0
    sp_votos = linhas[("SP", "votos")]
    assert (sp_votos["diferenca"], sp_votos["situacao"]) == (-2, "diverge")
    assert sp_votos["diferenca_pct"] == pytest.approx(-100 * 2 / 12)
    assert linhas[("RJ", "aptos")]["situacao"] == "so_nosso"
    assert linhas[("BA", "votos")]["situacao"] == "so_fonte"
    assert linhas[("BA", "votos")]["diferenca"] is None


def test_comparar_tolerancia_e_fonte_zero() -> None:
    nosso = pl.DataFrame({"k": [1, 2], "v": [10.004, 3.0]})
    fonte = pl.DataFrame({"k": [1, 2], "v": [10.0, 0.0]})
    df = conferencia.comparar(nosso, fonte, chaves=["k"], tolerancia=0.01)
    assert df["situacao"].to_list() == ["confere", "diverge"]
    assert df["diferenca_pct"].to_list()[1] is None


def test_comparar_medida_nula_na_fonte_e_descartada() -> None:
    # Majoritário: fonte sem legenda (null) → a medida não é comparada, não vira "só nosso".
    nosso = pl.DataFrame({"k": [1], "legenda": [0], "v": [1]})
    fonte = pl.DataFrame(
        {"k": [1], "legenda": [None], "v": [1]}, schema_overrides={"legenda": pl.Int64}
    )
    df = conferencia.comparar(nosso, fonte, chaves=["k"])
    assert df["medida"].to_list() == ["v"]


def test_comparar_medidas_diferentes_falha() -> None:
    with pytest.raises(ValueError, match="medidas"):
        conferencia.comparar(NOSSO, FONTE.rename({"votos": "x"}), chaves=["sg_uf"])


def test_comparar_chave_duplicada_falha() -> None:
    with pytest.raises(ValueError, match="duplicad"):
        conferencia.comparar(pl.concat([NOSSO, NOSSO]), FONTE, chaves=["sg_uf"])
