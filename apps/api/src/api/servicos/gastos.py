"""Caso de uso /gastos: custo por voto, receita por fonte e dependência de recursos públicos."""

from pydantic import BaseModel, ConfigDict

from api.repositorio.base import Repositorio
from api.servicos.contas import ResumoCustoCandidato, ResumoCustoGrupo, ResumoReceitasOut, contas_de
from api.servicos.grupos import Catalogo, candidaturas_do_grupo


class GastoCandidato(BaseModel):
    """Contas de um candidato do grupo."""

    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    receita_total: float
    custo: ResumoCustoCandidato


class Gastos(BaseModel):
    """Corpo de GET /gastos."""

    grupo: str
    ano: int
    cargo: str | None
    uf: str | None
    agregado: ResumoCustoGrupo
    receitas: ResumoReceitasOut
    por_candidato: list[GastoCandidato]
    contas_parciais: bool
    base_ipca: str | None
    dt_geracao: str

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
                    },
                    "por_candidato": [],
                    "contas_parciais": True,
                    "base_ipca": None,
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


def montar_gastos(
    repo: Repositorio, catalogo: Catalogo, *, grupo_id: str, uf: str | None, cargo: str | None
) -> Gastos:
    """Finanças do grupo no recorte; 2022 sai deflacionado (mês-base explícito)."""
    grupo = catalogo.grupo(grupo_id)
    contas = contas_de(repo, grupo.ano, candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo))
    return Gastos(
        grupo=grupo.id,
        ano=grupo.ano,
        cargo=cargo,
        uf=uf,
        agregado=contas.agregado,
        receitas=contas.receitas,
        por_candidato=[
            GastoCandidato(
                sq_candidato=c.candidatura.sq_candidato,
                nm_urna=c.candidatura.nm_urna,
                sg_uf=c.candidatura.sg_uf,
                cargo=c.candidatura.ds_cargo,
                receita_total=c.receita_total,
                custo=c.custo,
            )
            for c in contas.por_candidato
        ],
        contas_parciais=contas.parcial,
        base_ipca=contas.base_ipca,
        dt_geracao=repo.dt_geracao(),
    )
