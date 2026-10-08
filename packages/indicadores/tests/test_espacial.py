"""Bordas, erros e inferência de `indicadores.espacial` não cobertos pelos vetores."""

import polars as pl
import pytest
from indicadores import espacial


def test_tipologia_sem_populacao_de_referencia_e_nula() -> None:
    candidatos = pl.DataFrame(
        {"sq_candidato": ["a"], "votos": [1], "indice_g": [0.1], "dominancia_ames": [0.1]}
    )
    linha = espacial.tipologia_ames(candidatos, 1000).row(0, named=True)
    assert linha["mediana_g"] is None
    assert linha["tipo"] is None
    assert linha["na_populacao_referencia"] is False


def test_tipologia_qe_invalido_falha() -> None:
    candidatos = pl.DataFrame(
        {"sq_candidato": ["a"], "votos": [1], "indice_g": [0.1], "dominancia_ames": [0.1]}
    )
    with pytest.raises(ValueError, match="quociente eleitoral"):
        espacial.tipologia_ames(candidatos, 0)


def test_eb_por_grupo_e_taxa_zero() -> None:
    df = pl.DataFrame(
        {
            "sq_candidato": ["a", "a", "b", "b", "b"],
            "cd_mun_ibge": [1, 2, 1, 2, 3],
            "votos": [0, 0, 10, 20, 0],
            "aptos": [100, 200, 100, 200, 0],
        }
    )
    res = espacial.suavizacao_eb(df, por=("sq_candidato",)).sort("sq_candidato", "cd_mun_ibge")
    assert res.height == 4  # aptos = 0 fica fora
    assert res.filter(pl.col("sq_candidato") == "a")["taxa_eb"].to_list() == [0.0, 0.0]
    assert res.filter(pl.col("sq_candidato") == "b")["eb_b"].to_list() == [0.1, 0.1]


def _cadeia(valores: list[float]) -> tuple[pl.DataFrame, pl.DataFrame]:
    n = len(valores)
    arestas = [(i, i + 1) for i in range(n - 1)] + [(i + 1, i) for i in range(n - 1)]
    return (
        pl.DataFrame({"id": list(range(n)), "valor": valores}),
        pl.DataFrame(arestas, schema=["id", "vizinho"], orient="row"),
    )


def test_moran_permutacao_deterministica_e_significativa() -> None:
    valores, viz = _cadeia([float(i) for i in range(30)])
    r1 = espacial.moran_lisa(valores, viz, permutacoes=199)
    r2 = espacial.moran_lisa(valores, viz, permutacoes=199)
    assert r1.pseudo_p == r2.pseudo_p
    assert r1.locais.equals(r2.locais)
    assert r1.pseudo_p is not None
    assert r1.pseudo_p <= 0.01
    p = r1.locais["pseudo_p"]
    assert p.min() >= 1 / 200  # type: ignore[operator]
    assert p.max() <= 1.0  # type: ignore[operator]


def test_moran_autocorrelacao_negativa_tem_p_pequeno() -> None:
    valores, viz = _cadeia([float(i % 2) for i in range(30)])
    res = espacial.moran_lisa(valores, viz, permutacoes=99)
    assert res.moran_i is not None
    assert res.moran_i < 0
    assert res.pseudo_p is not None
    assert res.pseudo_p <= 0.05


def test_moran_variancia_zero_e_nulo() -> None:
    valores, viz = _cadeia([2.0, 2.0, 2.0])
    res = espacial.moran_lisa(valores, viz, permutacoes=9)
    assert res.moran_i is None
    assert res.pseudo_p is None
    assert res.locais["lisa"].to_list() == [None, None, None]


def test_moran_ilha_falha() -> None:
    valores = pl.DataFrame({"id": [0, 1, 2], "valor": [1.0, 2.0, 3.0]})
    viz = pl.DataFrame({"id": [0, 1], "vizinho": [1, 0]})
    with pytest.raises(ValueError, match="sem vizinho"):
        espacial.moran_lisa(valores, viz)


def test_moran_vizinho_desconhecido_falha() -> None:
    valores = pl.DataFrame({"id": [0, 1], "valor": [1.0, 2.0]})
    viz = pl.DataFrame({"id": [0, 1], "vizinho": [1, 7]})
    with pytest.raises(ValueError, match="desconhecid"):
        espacial.moran_lisa(valores, viz)


def test_moran_valor_nulo_falha() -> None:
    valores = pl.DataFrame({"id": [0, 1], "valor": [1.0, None]})
    viz = pl.DataFrame({"id": [0, 1], "vizinho": [1, 0]})
    with pytest.raises(ValueError, match="nul"):
        espacial.moran_lisa(valores, viz)


def test_cobertura_sem_votos_e_nula() -> None:
    locais = pl.DataFrame(
        {"cd_mun_ibge": [1], "h3_r8": [None], "aptos": [10], "votos": [0]},
        schema_overrides={"h3_r8": pl.String},
    )
    linha = espacial.cobertura_h3(locais, "h3_r8").row(0, named=True)
    assert linha["pct_votos_sem_coordenada"] is None
    assert linha["alerta_cobertura_h3"] is None


def test_h3_marca_n_baixo_pela_taxa_da_uf() -> None:
    locais = pl.DataFrame(
        {"cd_mun_ibge": [1, 1], "h3_r8": ["a", "b"], "aptos": [100, 10000], "votos": [1, 99]}
    )
    df = espacial.agregar_h3(locais, "h3_r8")
    assert df["n_baixo"].to_list() == [True, False]


def _anos(**valores: list[float | None]) -> dict[int, pl.DataFrame]:
    return {
        int(ano.removeprefix("a")): pl.DataFrame(
            {"valor": v, "n_baixo": [False] * len(v)},
            schema={"valor": pl.Float64, "n_baixo": pl.Boolean},
        )
        for ano, v in valores.items()
    }


def test_quebras_valor_nao_finito_falha() -> None:
    anos = _anos(a2022=[float(i) for i in range(10)] + [float("inf")])
    with pytest.raises(ValueError, match="não finito"):
        espacial.quebras_comuns(anos)


def test_quebras_nan_falha() -> None:
    anos = _anos(a2022=[float(i) for i in range(10)] + [float("nan")])
    with pytest.raises(ValueError, match="não finito"):
        espacial.quebras_comuns(anos)


def test_quebras_coluna_ausente_falha() -> None:
    with pytest.raises(ValueError, match="colunas ausentes"):
        espacial.quebras_comuns({2022: pl.DataFrame({"valor": [1.0] * 10})})


def test_quebras_sem_exclusao_dispensa_n_baixo() -> None:
    tabela = pl.DataFrame({"valor": [float(i) for i in range(1, 11)]})
    assert espacial.quebras_comuns({2026: tabela}, k=2, excluir_n_baixo=False) == [5.5]


def test_quebras_coluna_configuravel_e_estritamente_crescente() -> None:
    tabela = pl.DataFrame({"pct": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0]})
    quebras = espacial.quebras_comuns({2026: tabela}, excluir_n_baixo=False, coluna="pct")
    assert quebras == sorted(set(quebras))
    assert all(q > 0 for q in quebras)
