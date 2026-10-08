"""Finanças de campanha: despesas, receitas e custo por voto, com correção pelo IPCA.

Orquestração: lê do Repositorio, monta DataFrames e chama `indicadores.financeiro/grupos`.
Nenhuma fórmula local (spec §4); transferências e doações internas saem nas funções da lib.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl
from indicadores import financeiro, grupos
from pydantic import BaseModel, Field

from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura

ANO_NOMINAL = 2026  # valores de 2026 ficam nominais; anteriores sobem para o mês-base


class ResumoCustoCandidato(BaseModel):
    """Despesa (sem transferências) e custo por voto de um candidato."""

    despesa_contratada: float
    despesa_paga: float
    divida: float = Field(description="contratada − paga (§4.2).")
    votos: int
    custo_voto_contratado: float | None = Field(description="R$/voto; null se votos = 0.")
    custo_voto_pago: float | None


class ResumoReceitasOut(BaseModel):
    """Receita por categoria (§4.1) e dependência de recursos públicos."""

    por_categoria: dict[str, float]
    receita_total: float
    receita_financeira: float
    pct_publico: float | None = Field(description="FEFC + Fundo Partidário, % da receita total.")
    pct_autofinanciamento: float | None


class ResumoCustoGrupo(BaseModel):
    """Agregado: Σ despesa / Σ votos, não média de razões (§4.2)."""

    despesa_contratada: float
    despesa_paga: float
    divida: float
    votos: int
    custo_voto_contratado: float | None
    custo_voto_pago: float | None
    mediana_custo_voto_contratado: float | None
    candidatos_sem_voto_excluidos: int


@dataclass(frozen=True)
class ContasCand:
    """Contas de um candidato com a candidatura."""

    candidatura: Candidatura
    custo: ResumoCustoCandidato
    receita_total: float


@dataclass(frozen=True)
class ContasAgregadas:
    """Contas de um conjunto de candidaturas."""

    por_candidato: list[ContasCand]
    agregado: ResumoCustoGrupo
    receitas: ResumoReceitasOut
    parcial: bool
    base_ipca: str | None


_ESQUEMA_DESPESA = {
    "sq_candidato": pl.Int64,
    "ds_origem_despesa": pl.String,
    "vr_despesa_contratada": pl.Float64,
    "vr_despesa_paga": pl.Float64,
}
_ESQUEMA_RECEITA = {
    "sq_candidato": pl.Int64,
    "ds_fonte_receita": pl.String,
    "ds_origem_receita": pl.String,
    "ds_natureza_receita": pl.String,
    "vr_receita": pl.Float64,
    "sq_candidato_doador": pl.Int64,
}


def _correcao(repo: Repositorio, ano: int) -> tuple[pl.DataFrame, str, str] | None:
    """(série, mês de origem, mês-base efetivo) ou `None` se o ano é nominal.

    O mês-base é o do ADR 0007 se já publicado, senão o último disponível — e a resposta o
    declara (`base_ipca`). Sem série utilizável não se publica 2022 "nominal" por engano.
    """
    if ano >= ANO_NOMINAL:
        return None
    serie = financeiro.serie_ipca({v.mes: v.variacao for v in repo.ipca()})
    origem = f"{ano}-09"
    try:
        return serie, origem, financeiro.resolver_mes_base(serie, origem)
    except ValueError as erro:
        raise DadosIndisponiveis(str(erro)) from erro


def _corrigir(
    df: pl.DataFrame, colunas: Sequence[str], correcao: tuple[pl.DataFrame, str, str] | None
) -> pl.DataFrame:
    if correcao is None:
        return df
    serie, origem, base = correcao
    try:
        for coluna in colunas:
            df = financeiro.corrigir_ipca(df, coluna, serie, origem, base)
    except ValueError as erro:  # mês faltando na série
        raise DadosIndisponiveis(str(erro)) from erro
    return df


def contas_de(repo: Repositorio, ano: int, candidaturas: Sequence[Candidatura]) -> ContasAgregadas:
    """Contas das candidaturas no ano; só entram candidatos com lançamentos."""
    sqs = [c.sq_candidato for c in candidaturas]
    correcao = _correcao(repo, ano)
    votos = repo.votos_totais(ano, sqs)
    despesas = pl.DataFrame(
        [
            (d.sq_candidato, d.ds_origem_despesa, d.contratada, d.paga)
            for d in repo.despesas(ano, sqs)
        ],
        schema=_ESQUEMA_DESPESA,
        orient="row",
    )
    receitas = pl.DataFrame(
        [
            (r.sq_candidato, r.ds_fonte_receita, r.ds_origem_receita, r.ds_natureza_receita,
             r.valor, r.sq_candidato_doador)
            for r in repo.receitas(ano, sqs)
        ],
        schema=_ESQUEMA_RECEITA,
        orient="row",
    )  # fmt: skip
    receitas = _corrigir(receitas, ["vr_receita"], correcao)
    com_contas = set(despesas["sq_candidato"]) | set(receitas["sq_candidato"])

    contratada = financeiro.despesa_campanha(despesas, "vr_despesa_contratada").rename(
        {"despesa": "despesa_contratada"}
    )
    paga = financeiro.despesa_campanha(despesas, "vr_despesa_paga").rename(
        {"despesa": "despesa_paga"}
    )
    tem_contas = pl.col("sq_candidato").is_in(list(com_contas))
    # Quem tem lançamentos mas só repasses fica com despesa 0; quem não tem contas fica null
    # (a lib exclui "sem contas" do agregado).
    base = (
        pl.DataFrame(
            {"sq_candidato": sqs, "votos": [votos.get(sq, 0) for sq in sqs]},
            schema={"sq_candidato": pl.Int64, "votos": pl.Int64},
        )
        .join(contratada, on="sq_candidato", how="left")
        .join(paga, on="sq_candidato", how="left")
        .with_columns(
            pl.when(tem_contas).then(pl.col(c).fill_null(0.0)).otherwise(None).alias(c)
            for c in ("despesa_contratada", "despesa_paga")
        )
    )
    base = _corrigir(base, ["despesa_contratada", "despesa_paga"], correcao)
    por_cand = financeiro.custo_por_voto(base).filter(pl.col("despesa_contratada").is_not_null())

    classificadas = financeiro.classificar_receitas(receitas)
    totais_cand = {
        linha["sq_candidato"]: linha["receita_total"]
        for linha in financeiro.resumo_receitas(classificadas).to_dicts()
    }
    resumo_rec = grupos.receitas_grupo(classificadas, sqs).to_dicts()[0]
    agg = financeiro.custo_por_voto_agregado(base).to_dicts()[0]
    soma = financeiro.custo_por_voto(
        por_cand.select(
            pl.col("despesa_contratada").sum(),
            pl.col("despesa_paga").sum(),
            pl.col("votos").sum(),
        )
    ).to_dicts()[0]
    por_sq = {c.sq_candidato: c for c in candidaturas}
    return ContasAgregadas(
        por_candidato=[
            ContasCand(
                candidatura=por_sq[linha["sq_candidato"]],
                custo=ResumoCustoCandidato(
                    despesa_contratada=linha["despesa_contratada"],
                    despesa_paga=linha["despesa_paga"],
                    divida=linha["divida"],
                    votos=linha["votos"],
                    custo_voto_contratado=linha["custo_voto_contratado"],
                    custo_voto_pago=linha["custo_voto_pago"],
                ),
                receita_total=totais_cand.get(linha["sq_candidato"], 0.0),
            )
            for linha in por_cand.to_dicts()
        ],
        agregado=ResumoCustoGrupo(
            despesa_contratada=soma["despesa_contratada"],
            despesa_paga=soma["despesa_paga"],
            divida=soma["divida"],
            votos=soma["votos"],
            custo_voto_contratado=agg["custo_voto_contratado"],
            custo_voto_pago=agg["custo_voto_pago"],
            mediana_custo_voto_contratado=agg["mediana_custo_voto_contratado"],
            candidatos_sem_voto_excluidos=agg["candidatos_sem_voto_excluidos"],
        ),
        receitas=ResumoReceitasOut(
            por_categoria={
                c: resumo_rec[f"receita_{c}"]
                for c in financeiro.CATEGORIAS_RECEITA
                if resumo_rec[f"receita_{c}"]
            },
            receita_total=resumo_rec["receita_total"],
            receita_financeira=resumo_rec["receita_financeira"],
            pct_publico=resumo_rec["pct_publico"],
            pct_autofinanciamento=resumo_rec["pct_autofinanciamento"],
        ),
        parcial=repo.tp_prestacao_contas(ano).upper() == "PARCIAL",
        base_ipca=correcao[2] if correcao else None,
    )
