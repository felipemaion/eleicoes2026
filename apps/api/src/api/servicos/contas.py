"""Finanças de campanha: despesas, receitas e custo por voto, com correção pelo IPCA."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field

from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos import adaptador_indicadores as ind

MES_ORIGEM_2022 = "2022-09"
MES_BASE_IPCA = "2026-09"  # decisão 1.6 da spec: set/2022 → set/2026
ANO_NOMINAL = 2026


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


def _fator(repo: Repositorio, ano: int) -> float:
    if ano >= ANO_NOMINAL:
        return 1.0
    serie = {v.mes: v.variacao for v in repo.ipca()}
    try:
        return ind.fator_ipca(serie, f"{ano}-09", MES_BASE_IPCA)
    except ValueError as erro:
        # Sem IPCA não se publica valor de 2022 "nominal" por engano.
        raise DadosIndisponiveis(str(erro)) from erro


def contas_de(repo: Repositorio, ano: int, candidaturas: Sequence[Candidatura]) -> ContasAgregadas:
    """Contas das candidaturas no ano; só entram candidatos com lançamentos."""
    sqs = [c.sq_candidato for c in candidaturas]
    fator = _fator(repo, ano)
    votos = repo.votos_totais(ano, sqs)
    despesas = repo.despesas(ano, sqs)
    receitas = repo.receitas(ano, sqs)
    com_contas = {d.sq_candidato for d in despesas} | {r.sq_candidato for r in receitas}
    cands = [c for c in candidaturas if c.sq_candidato in com_contas]
    contas = []
    for c in cands:
        proprias = [d for d in despesas if d.sq_candidato == c.sq_candidato]
        validas = [d for d in proprias if not ind.eh_transferencia(d.ds_origem_despesa)]
        contas.append(
            ind.ContasCandidato(
                c.sq_candidato,
                sum(d.contratada for d in validas) * fator,
                sum(d.paga for d in validas) * fator,
                votos.get(c.sq_candidato, 0),
            )
        )
    custos, grupo = ind.custo_por_voto(contas)
    receita_por_cand = {
        c.sq_candidato: sum(r.valor for r in receitas if r.sq_candidato == c.sq_candidato) * fator
        for c in cands
    }
    resumo_rec = ind.resumir_receitas(
        ind.LinhaReceita(
            r.ds_fonte_receita, r.ds_origem_receita, r.ds_natureza_receita, r.valor * fator
        )
        for r in receitas
    )
    return ContasAgregadas(
        por_candidato=[
            ContasCand(
                candidatura=c,
                custo=ResumoCustoCandidato(
                    despesa_contratada=ct.despesa_contratada,
                    despesa_paga=ct.despesa_paga,
                    divida=cu.divida,
                    votos=ct.votos,
                    custo_voto_contratado=cu.custo_voto_contratado,
                    custo_voto_pago=cu.custo_voto_pago,
                ),
                receita_total=receita_por_cand[c.sq_candidato],
            )
            for c, ct, cu in zip(cands, contas, custos, strict=True)
        ],
        agregado=ResumoCustoGrupo(
            despesa_contratada=grupo.despesa_contratada,
            despesa_paga=grupo.despesa_paga,
            divida=grupo.divida,
            votos=grupo.votos,
            custo_voto_contratado=grupo.custo_voto_contratado,
            custo_voto_pago=grupo.custo_voto_pago,
            mediana_custo_voto_contratado=grupo.mediana_custo_voto_contratado,
            candidatos_sem_voto_excluidos=grupo.candidatos_sem_voto_excluidos,
        ),
        receitas=ResumoReceitasOut(
            por_categoria=resumo_rec.por_categoria,
            receita_total=resumo_rec.receita_total,
            receita_financeira=resumo_rec.receita_financeira,
            pct_publico=resumo_rec.pct_publico,
            pct_autofinanciamento=resumo_rec.pct_autofinanciamento,
        ),
        parcial=repo.tp_prestacao_contas(ano).upper() == "PARCIAL",
        base_ipca=MES_BASE_IPCA if ano < ANO_NOMINAL else None,
    )
