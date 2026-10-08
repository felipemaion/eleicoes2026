"""Cada caso de cada vetor da spec (docs/metodologia/vetores/*.json) contra a implementação.

Um adaptador por indicador traduz a `entrada` do vetor numa chamada da biblioteca e devolve
uma estrutura comparável à `saida`. A comparação é recursiva: dicionários comparam só as
chaves esperadas, números com a `tolerancia_absoluta` do vetor, `null` exige `None`.
"""

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from indicadores import desempenho, espacial, evolucao, financeiro

RAIZ = Path(__file__).resolve().parents[3]
VETORES = RAIZ / "docs" / "metodologia" / "vetores"

Adaptador = Callable[[Any], Any]


def _linhas(df: pl.DataFrame) -> list[dict[str, Any]]:
    return df.to_dicts()


def _tabela(entrada: dict[str, Any]) -> pl.DataFrame:
    return desempenho.indicadores_municipais(
        pl.DataFrame(entrada["votos"]), pl.DataFrame(entrada["municipios"])
    )


def _municipal_e_uf(entrada: dict[str, Any]) -> list[dict[str, Any]]:
    municipal = _tabela(entrada).sort("sq_candidato", "cd_mun_ibge")
    uf = desempenho.totais_uf(municipal).with_columns(
        pl.lit(None, dtype=pl.Int64).alias("cd_mun_ibge"), pl.lit("UF").alias("recorte")
    )
    linhas = _linhas(municipal)
    # O caso do senado (um município) só lista linhas municipais; os demais terminam na UF.
    return linhas + _linhas(uf) if municipal["cd_mun_ibge"].n_unique() > 1 else linhas


def _votos_nominais(entrada: dict[str, Any]) -> list[dict[str, Any]]:
    df = desempenho.votos_nominais(pl.DataFrame(entrada["votacao_candidato_munzona"]))
    return _linhas(df)


def _votos_legenda(entrada: dict[str, Any]) -> dict[str, Any]:
    qe = desempenho.quociente_eleitoral(entrada["qt_total_votos_validos_uf"], entrada["vagas"])
    if "votacao_partido" not in entrada:
        return {"quociente_eleitoral": qe}
    partidos = pl.DataFrame(entrada["votacao_partido"]).with_columns(
        pl.lit(entrada["nominais_validos_candidatos_partido"]).alias("votos_nominais_validos"),
        pl.lit(entrada["qt_total_votos_validos_uf"]).alias("qt_total_votos_validos_uf"),
        pl.lit(entrada["vagas"]).alias("vagas"),
    )
    return _linhas(desempenho.votacao_partido(partidos))[0]


def _votos_km2(entrada: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _linhas(desempenho.votos_km2(pl.DataFrame(entrada)))


def _n_baixo(entrada: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _linhas(espacial.n_baixo(pl.DataFrame(entrada)))


def _lq(entrada: dict[str, Any]) -> list[dict[str, Any]]:
    return _linhas(_tabela(entrada).sort("cd_mun_ibge"))


def _concentracao(entrada: dict[str, Any]) -> dict[str, Any]:
    return _linhas(espacial.concentracao(_tabela(entrada)))[0]


def _tipologia(entrada: dict[str, Any]) -> dict[str, Any]:
    df = espacial.tipologia_ames(
        pl.DataFrame(entrada["candidatos"]), entrada["quociente_eleitoral"]
    )
    primeira = df.row(0, named=True)
    return {
        "limiar_votos": primeira["limiar_votos"],
        "mediana_g": primeira["mediana_g"],
        "mediana_dominancia": primeira["mediana_dominancia"],
        "candidatos": _linhas(df.sort("sq_candidato")),
    }


def _eb(entrada: list[dict[str, Any]]) -> dict[str, Any]:
    df = espacial.suavizacao_eb(pl.DataFrame(entrada)).sort("cd_mun_ibge")
    primeira = df.row(0, named=True)
    return {"b": primeira["eb_b"], "a": primeira["eb_a"], "municipios": _linhas(df)}


def _moran(entrada: dict[str, Any]) -> dict[str, Any]:
    valores = pl.DataFrame(
        {"id": list(range(len(entrada["valores"]))), "valor": entrada["valores"]}
    )
    arestas = [(int(i), j) for i, viz in entrada["vizinhos"].items() for j in viz]
    vizinhanca = pl.DataFrame(arestas, schema=["id", "vizinho"], orient="row")
    res = espacial.moran_lisa(valores, vizinhanca, permutacoes=0)
    locais = res.locais.sort("id")
    return {
        "moran_i": res.moran_i,
        "lisa": locais["lisa"].to_list(),
        "quadrante": locais["quadrante"].to_list(),
    }


def _h3(entrada: list[dict[str, Any]]) -> dict[str, Any]:
    locais = pl.DataFrame(entrada)
    return {
        "r8": _linhas(espacial.agregar_h3(locais, "h3_r8")),
        "r7": _linhas(espacial.agregar_h3(locais, "h3_r7")),
        "municipio": _linhas(espacial.cobertura_h3(locais, "h3_r8"))[0],
    }


_ESQUEMA_RECEITAS = {
    "sq_candidato": pl.String,
    "ds_fonte_receita": pl.String,
    "ds_origem_receita": pl.String,
    "ds_natureza_receita": pl.String,
    "vr_receita": pl.Float64,
}


def _receitas(entrada: list[dict[str, Any]]) -> dict[str, Any]:
    df = financeiro.resumo_receitas(
        financeiro.classificar_receitas(pl.DataFrame(entrada, schema=_ESQUEMA_RECEITAS)), por=()
    )
    linha = df.row(0, named=True)
    linha["por_categoria"] = {
        c: linha[f"receita_{c}"] for c in financeiro.CATEGORIAS_RECEITA if linha[f"receita_{c}"]
    }
    return linha


def _custo(entrada: Any) -> dict[str, Any]:
    if isinstance(entrada, dict):
        despesa = financeiro.despesa_campanha(
            pl.DataFrame(entrada["despesas_contratadas"]), "vr_despesa_contratada"
        )
        valor = despesa["despesa"].item()
        custo = financeiro.custo_por_voto(
            pl.DataFrame(
                {
                    "sq_candidato": ["x"],
                    "despesa_contratada": [valor],
                    "despesa_paga": [valor],
                    "votos": [entrada["votos"]],
                }
            )
        )
        return {"despesa_contratada": valor, **_linhas(custo)[0]}
    df = pl.DataFrame(entrada)
    return {
        "candidatos": _linhas(financeiro.custo_por_voto(df)),
        "grupo": _linhas(financeiro.custo_por_voto_agregado(df))[0],
    }


def _ipca(entrada: dict[str, Any]) -> dict[str, Any]:
    serie = financeiro.serie_ipca(entrada["ipca_variacao_mensal"])
    fator = financeiro.fator_ipca(serie, entrada["mes_origem"], entrada["mes_base"])
    corrigido = financeiro.corrigir_ipca(
        pl.DataFrame({"valor": [entrada["valor"]]}),
        "valor",
        serie,
        entrada["mes_origem"],
        entrada["mes_base"],
    )
    return {"fator": fator, "valor_base": corrigido["valor"].item()}


def _evolucao(entrada: dict[str, Any]) -> list[dict[str, Any]]:
    amc = pl.DataFrame(
        {"cd_mun_ibge": [int(k) for k in entrada["amc"]], "amc": list(entrada["amc"].values())}
    )
    df = evolucao.evolucao(
        pl.DataFrame(entrada["ano_2022"]), pl.DataFrame(entrada["ano_2026"]), amc
    )
    return _linhas(df.sort("amc"))


def _redutos(entrada: list[dict[str, Any]]) -> dict[str, Any]:
    return _linhas(evolucao.sobreposicao_redutos(pl.DataFrame(entrada)))[0]


def _por_candidato(entrada: dict[str, Any]) -> dict[str, Any]:
    if "ano_2022" in entrada:
        df = evolucao.mesmos_candidatos(
            pl.DataFrame(entrada["ano_2022"]), pl.DataFrame(entrada["ano_2026"])
        )
        return _linhas(df)[0]
    saida: dict[str, Any] = {}
    for chave, grupo in entrada.items():
        sufixo = chave.removeprefix("grupo")
        linha = _linhas(evolucao.por_candidato(pl.DataFrame([grupo])))[0]
        saida.update({f"{k}{sufixo}": v for k, v in linha.items()})
    return saida


def _quebras(entrada: dict[str, Any]) -> dict[str, Any]:
    tabelas = {
        int(ano): pl.DataFrame(linhas, schema={"valor": pl.Float64, "n_baixo": pl.Boolean})
        for ano, linhas in entrada["valores_por_ano"].items()
    }
    limiares = espacial.quebras_comuns(
        tabelas, k=entrada["k"], excluir_n_baixo=entrada["excluir_n_baixo"]
    )
    return {"quebras": limiares}


ADAPTADORES: dict[str, Adaptador] = {
    "votos_nominais": _votos_nominais,
    "pct_validos": _municipal_e_uf,
    "penetracao": _municipal_e_uf,
    "votos_legenda": _votos_legenda,
    "votos_km2": _votos_km2,
    "n_baixo": _n_baixo,
    "lq": _lq,
    "concentracao": _concentracao,
    "tipologia_ames": _tipologia,
    "suavizacao_eb": _eb,
    "moran_lisa": _moran,
    "agregacao_h3": _h3,
    "receitas": _receitas,
    "custo_por_voto": _custo,
    "deflacao_ipca": _ipca,
    "evolucao": _evolucao,
    "sobreposicao_redutos": _redutos,
    "por_candidato": _por_candidato,
    "quebras_comuns": _quebras,
}


def _casos() -> list[Any]:
    casos = []
    for caminho in sorted(VETORES.glob("*.json")):
        vetor = json.loads(caminho.read_text(encoding="utf-8"))
        for caso in vetor["casos"]:
            casos.append(
                pytest.param(
                    vetor["indicador"],
                    vetor["tolerancia_absoluta"],
                    caso,
                    id=f"{vetor['indicador']}::{caso['nome']}",
                )
            )
    return casos


def _comparar(obtido: Any, esperado: Any, tol: float, caminho: str) -> None:
    if esperado is None:
        assert obtido is None, f"{caminho}: esperado null, obtido {obtido!r}"
    elif isinstance(esperado, bool | str):
        assert obtido == esperado, f"{caminho}: {obtido!r} != {esperado!r}"
    elif isinstance(esperado, int | float):
        assert obtido is not None, f"{caminho}: obtido null, esperado {esperado}"
        assert not isinstance(obtido, bool), f"{caminho}: obtido booleano"
        assert math.isfinite(obtido), f"{caminho}: obtido {obtido}"
        assert abs(obtido - esperado) <= tol, f"{caminho}: {obtido} != {esperado} (tol {tol})"
    elif isinstance(esperado, dict):
        assert isinstance(obtido, dict), f"{caminho}: esperado objeto"
        for chave, valor in esperado.items():
            assert chave in obtido, f"{caminho}: falta a chave {chave!r}"
            _comparar(obtido[chave], valor, tol, f"{caminho}.{chave}")
    elif isinstance(esperado, list):
        assert isinstance(obtido, list), f"{caminho}: esperada lista"
        assert len(obtido) == len(esperado), f"{caminho}: {len(obtido)} != {len(esperado)} itens"
        for i, (o, e) in enumerate(zip(obtido, esperado, strict=True)):
            _comparar(o, e, tol, f"{caminho}[{i}]")
    else:  # pragma: no cover - tipo JSON inesperado no vetor
        pytest.fail(f"{caminho}: tipo inesperado {type(esperado)}")


def test_todo_vetor_tem_adaptador() -> None:
    existentes = {p.stem for p in VETORES.glob("*.json")}
    assert existentes == set(ADAPTADORES)


@pytest.mark.parametrize(("indicador", "tol", "caso"), _casos())
def test_caso_do_vetor(indicador: str, tol: float, caso: dict[str, Any]) -> None:
    adaptador = ADAPTADORES[indicador]
    if "erro" in caso:
        tipo, _, mensagem = caso["erro"].partition(": ")
        assert tipo == "ValueError"
        with pytest.raises(ValueError, match=mensagem):
            adaptador(caso["entrada"])
    else:
        _comparar(adaptador(caso["entrada"]), caso["saida"], tol, caso["nome"])
