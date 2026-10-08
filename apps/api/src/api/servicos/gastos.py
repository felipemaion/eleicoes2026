"""Caso de uso /gastos: custo por voto, receita por fonte e dependência de recursos públicos."""

from pydantic import BaseModel, ConfigDict, Field

from api.fontes import Fonte, fontes
from api.fotos import ComFotoELink, foto_e_link
from api.repositorio.base import Repositorio
from api.servicos.candidatos import Partido
from api.servicos.contas import (
    DistribuicaoReceita,
    ReceitaPorVotoGrupo,
    ResumoCustoCandidato,
    ResumoCustoGrupo,
    ResumoReceitasOut,
    SaldoGrupo,
    contas_de,
)
from api.servicos.grupos import Catalogo, candidaturas_do_grupo


class GastoCandidato(ComFotoELink):
    """Contas de um candidato do grupo."""

    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    partido: Partido
    resultado: str | None = Field(description="`ds_sit_tot_turno`; null até a apuração.")
    receita_total: float
    pct_publico: float | None = Field(
        description="FEFC + Fundo Partidário, % da receita do candidato."
    )
    pct_autofinanciamento: float | None
    pct_pessoa_fisica: float | None = Field(
        description="Pessoa física + financiamento coletivo, %."
    )
    n_efetivo_fontes: float | None = Field(description="1 / HHI das categorias de receita (§4.5).")
    receita_repasses_candidatos: float = Field(description="Recebido de outros candidatos (§4.6).")
    receita_sem_repasses: float
    receita_por_voto: float | None = Field(description="R$/voto = receita ÷ votos (§4.7).")
    receita_por_mil_aptos: float | None = Field(description="R$ por mil aptos da circunscrição.")
    saldo_contratado: float | None = Field(
        description="receita − despesa contratada, com repasses (§4.8)."
    )
    saldo_financeiro: float | None
    pct_receita_gasta: float | None
    custo: ResumoCustoCandidato


class Gastos(BaseModel):
    """Corpo de GET /gastos."""

    grupo: str
    ano: int
    cargo: str | None
    uf: str | None
    agregado: ResumoCustoGrupo
    receitas: ResumoReceitasOut
    receita_por_voto: ReceitaPorVotoGrupo
    distribuicao_receita: DistribuicaoReceita
    saldo: SaldoGrupo
    receita_por_mil_aptos: float | None = Field(
        description="1000 × receita do grupo ÷ aptos da circunscrição, contados uma vez (§4.7); "
        "null com mais de um cargo."
    )
    aptos: int | None = Field(description="Eleitorado usado em `receita_por_mil_aptos`.")
    por_candidato: list[GastoCandidato]
    contas_parciais: bool
    base_ipca: str | None
    dt_geracao: str
    fontes: list[Fonte] = Field(description="Procedência dos números (arquivo, regra, spec).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grupo": "missao_2026",
                    "ano": 2026,
                    "cargo": "DEPUTADO FEDERAL",
                    "uf": "SP",
                    "agregado": {
                        "despesa_contratada": 105000.0,
                        "despesa_paga": 85000.0,
                        "divida": 20000.0,
                        "votos": 1180,
                        "custo_voto_contratado": 88.98,
                        "custo_voto_pago": 72.03,
                        "mediana_custo_voto_contratado": 63.89,
                        "candidatos_sem_voto_excluidos": 0,
                    },
                    "receitas": {
                        "por_categoria": {"fefc": 70000.0, "fundo_partidario": 10000.0},
                        "receita_total": 118000.0,
                        "receita_financeira": 116000.0,
                        "pct_publico": 67.8,
                        "pct_autofinanciamento": 8.47,
                        "pct_pessoa_fisica": 21.2,
                        "n_efetivo_fontes": 2.1,
                        "receita_repasses_internos": 7000.0,
                        "faixa_receita": {"minima": 118000.0, "maxima": 118000.0},
                    },
                    "receita_por_voto": {
                        "receita_por_voto": 100.0,
                        "mediana_receita_por_voto": 96.4,
                        "candidatos_sem_voto_excluidos": 0,
                        "candidatos_sem_contas_excluidos": 0,
                    },
                    "saldo": {
                        "saldo_contratado": 19600.0,
                        "saldo_financeiro": 39600.0,
                        "pct_receita_gasta": 84.3,
                    },
                    "receita_por_mil_aptos": 7866.7,
                    "aptos": 15000,
                    "por_candidato": [],
                    "contas_parciais": True,
                    "base_ipca": None,
                    "dt_geracao": "2026-10-06",
                    "fontes": [],
                }
            ]
        }
    )


def montar_gastos(
    repo: Repositorio, catalogo: Catalogo, *, grupo_id: str, uf: str | None, cargo: str | None
) -> Gastos:
    """Finanças do grupo no recorte; 2022 sai deflacionado (mês-base explícito)."""
    grupo = catalogo.grupo(grupo_id)
    fotos = repo.fotos()
    contas = contas_de(repo, grupo.ano, candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo))
    return Gastos(
        grupo=grupo.id,
        ano=grupo.ano,
        cargo=cargo,
        uf=uf,
        agregado=contas.agregado,
        receitas=contas.receitas,
        receita_por_voto=contas.receita_por_voto,
        distribuicao_receita=contas.distribuicao,
        saldo=contas.saldo,
        receita_por_mil_aptos=contas.receita_por_mil_aptos,
        aptos=contas.aptos,
        por_candidato=[
            GastoCandidato(
                sq_candidato=c.candidatura.sq_candidato,
                nm_urna=c.candidatura.nm_urna,
                sg_uf=c.candidatura.sg_uf,
                cargo=c.candidatura.ds_cargo,
                partido=Partido(numero=c.candidatura.nr_partido, sigla=c.candidatura.sg_partido),
                resultado=c.candidatura.ds_sit_tot_turno,
                receita_total=c.receita_total,
                pct_publico=c.pct_publico,
                pct_autofinanciamento=c.pct_autofinanciamento,
                pct_pessoa_fisica=c.resumo.get("pct_pessoa_fisica"),
                n_efetivo_fontes=c.resumo.get("n_efetivo_fontes"),
                receita_repasses_candidatos=c.resumo.get("receita_repasses_candidatos") or 0.0,
                receita_sem_repasses=c.resumo.get("receita_sem_repasses") or 0.0,
                receita_por_voto=c.receita_por_voto,
                receita_por_mil_aptos=c.receita_por_mil_aptos,
                saldo_contratado=c.saldo_contratado,
                saldo_financeiro=c.saldo_financeiro,
                pct_receita_gasta=c.pct_receita_gasta,
                custo=c.custo,
                **foto_e_link(
                    fotos,
                    ano=grupo.ano,
                    sq_candidato=c.candidatura.sq_candidato,
                    uf=c.candidatura.sg_uf,
                ),
            )
            for c in contas.por_candidato
        ],
        contas_parciais=contas.parcial,
        base_ipca=contas.base_ipca,
        dt_geracao=repo.dt_geracao(),
        fontes=fontes(
            ["prestacao_contas", "votacao_candidato_munzona"]
            + (["ipca"] if contas.base_ipca else []),
            ano=grupo.ano,
            dt_geracao=repo.dt_geracao(),
        ),
    )
