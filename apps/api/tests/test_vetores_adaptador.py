"""Adaptador de indicadores (TODO(T-A02)) contra os vetores da spec — mesma tolerância."""

import json
from pathlib import Path
from typing import Any

import pytest
from api.servicos import adaptador_indicadores as ind

VETORES = Path(__file__).resolve().parents[3] / "docs" / "metodologia" / "vetores"


def _vetor(nome: str) -> dict[str, Any]:
    return json.loads((VETORES / f"{nome}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _caso(nome: str, caso: str) -> dict[str, Any]:
    return next(c for c in _vetor(nome)["casos"] if c["nome"] == caso)


def test_penetracao_e_pct_validos_por_municipio_e_uf() -> None:
    for indicador, funcao in (("penetracao", ind.penetracao), ("pct_validos", ind.pct_validos)):
        vetor = _vetor(indicador)
        tol = vetor["tolerancia_absoluta"]
        for caso in vetor["casos"]:
            muns = {m["cd_mun_ibge"]: m for m in caso["entrada"]["municipios"]}
            denominador = "aptos" if indicador == "penetracao" else "validos"
            for esperado in caso["saida"]:
                if esperado["cd_mun_ibge"] is None:  # recorte UF: Σvotos / Σdenominador
                    votos = esperado["votos"]
                    den = sum(m[denominador] for m in muns.values())
                else:
                    votos = esperado["votos"]
                    den = muns[esperado["cd_mun_ibge"]][denominador]
                obtido = funcao(votos, den)
                if esperado[indicador] is None:
                    assert obtido is None, caso["nome"]
                else:
                    assert obtido == pytest.approx(esperado[indicador], abs=tol), caso["nome"]


def test_receitas_vetor() -> None:
    caso = _caso("receitas", "c1_todas_as_categorias")
    linhas = [
        ind.LinhaReceita(
            fonte=r["ds_fonte_receita"],
            origem=r["ds_origem_receita"],
            natureza=r["ds_natureza_receita"],
            valor=r["vr_receita"],
        )
        for r in caso["entrada"]
    ]
    resumo = ind.resumir_receitas(linhas)
    esperado = caso["saida"]
    assert resumo.por_categoria == esperado["por_categoria"]
    assert resumo.receita_total == esperado["receita_total"]
    assert resumo.receita_financeira == esperado["receita_financeira"]
    assert resumo.pct_publico == pytest.approx(esperado["pct_publico"])
    assert resumo.pct_autofinanciamento == pytest.approx(esperado["pct_autofinanciamento"])


def test_receitas_sem_dados_tem_taxas_nulas() -> None:
    resumo = ind.resumir_receitas([])
    assert resumo.receita_total == 0.0
    assert resumo.pct_publico is None
    assert resumo.pct_autofinanciamento is None


def test_receitas_rotulo_desconhecido_falha_alto() -> None:
    with pytest.raises(ValueError, match="ds_fonte_receita desconhecida"):
        ind.classificar_receita("FUNDO NOVO", "Recursos de pessoas físicas")
    with pytest.raises(ValueError, match="ds_origem_receita desconhecida"):
        ind.classificar_receita("OUTROS RECURSOS", "Origem inventada")


def test_custo_por_voto_vetor() -> None:
    caso = _caso("custo_por_voto", "candidatos_e_agregado")
    entrada = [
        ind.ContasCandidato(
            c["sq_candidato"], c["despesa_contratada"], c["despesa_paga"], c["votos"]
        )
        for c in caso["entrada"]
    ]
    candidatos, grupo = ind.custo_por_voto(entrada)
    for obtido, esperado in zip(candidatos, caso["saida"]["candidatos"], strict=True):
        assert obtido.sq_candidato == esperado["sq_candidato"]
        for campo in ("custo_voto_contratado", "custo_voto_pago", "divida"):
            valor = getattr(obtido, campo)
            if esperado[campo] is None:
                assert valor is None
            else:
                assert valor == pytest.approx(esperado[campo], abs=1e-6)
    esp = caso["saida"]["grupo"]
    assert grupo.custo_voto_contratado == pytest.approx(esp["custo_voto_contratado"], abs=1e-6)
    assert grupo.custo_voto_pago == pytest.approx(esp["custo_voto_pago"], abs=1e-6)
    assert grupo.candidatos_sem_voto_excluidos == esp["candidatos_sem_voto_excluidos"]


def test_deflacao_ipca_vetor() -> None:
    for caso in _vetor("deflacao_ipca")["casos"]:
        e = caso["entrada"]
        if "erro" in caso:
            with pytest.raises(ValueError, match="IPCA ausente para 2022-11"):
                ind.fator_ipca(e["ipca_variacao_mensal"], e["mes_origem"], e["mes_base"])
        else:
            fator = ind.fator_ipca(e["ipca_variacao_mensal"], e["mes_origem"], e["mes_base"])
            assert fator == pytest.approx(caso["saida"]["fator"], abs=1e-6)
            assert e["valor"] * fator == pytest.approx(caso["saida"]["valor_base"], abs=1e-6)


def test_evolucao_vetor() -> None:
    caso = _vetor("evolucao")["casos"][0]
    e = caso["entrada"]
    cru = lambda linhas: [  # noqa: E731
        ind.BaseMunicipio(r["cd_mun_ibge"], r["aptos"], r["validos"], r["votos"]) for r in linhas
    ]
    amc = {int(k): v for k, v in e["amc"].items()}
    obtidos = ind.evolucao(amc, cru(e["ano_2022"]), cru(e["ano_2026"]))
    assert len(obtidos) == len(caso["saida"])
    for obtido, esperado in zip(obtidos, caso["saida"], strict=True):
        assert obtido.amc == esperado["amc"]
        assert obtido.ganho_absoluto == esperado["ganho_absoluto"]
        for campo in (
            "penetracao_2022",
            "penetracao_2026",
            "delta_penetracao",
            "swing_pp",
            "retencao",
        ):
            valor = getattr(obtido, campo)
            if esperado[campo] is None:
                assert valor is None, campo
            else:
                assert valor == pytest.approx(esperado[campo], abs=1e-9), campo


def test_evolucao_municipio_fora_do_crosswalk_falha_alto() -> None:
    with pytest.raises(ValueError, match="AMC ausente"):
        ind.evolucao({}, [ind.BaseMunicipio(1, 10, 8, 1)], [])
