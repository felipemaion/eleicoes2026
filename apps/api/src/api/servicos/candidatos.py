"""Casos de uso /candidatos e /candidatos/{ano}/{sq}."""

import polars as pl
from indicadores import desempenho
from pydantic import BaseModel, ConfigDict, Field

from api.erros import nao_encontrado
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.contas import (
    ResumoCustoCandidato,
    ResumoReceitasOut,
    contas_de,
)
from api.servicos.escopo import BasesPorEscopo, uf_da_base
from api.servicos.grupos import Catalogo, candidaturas_do_grupo


class Partido(BaseModel):
    """Partido da candidatura."""

    numero: int
    sigla: str


class CandidatoResumo(BaseModel):
    """Candidato com votos e taxas na sua circunscrição (cargo × UF)."""

    ano: int
    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    partido: Partido
    situacao: str = Field(description="`ds_situacao_candidatura` (APTO, INDEFERIDO…).")
    resultado: str | None = Field(
        description="`ds_sit_tot_turno` (ELEITO, SUPLENTE…); null se sem apuração."
    )
    votos: int = Field(description="Votos nominais válidos (spec §2.1).")
    pct_validos: float | None = Field(description="% dos válidos do cargo na UF (§2.2).")
    penetracao: float | None = Field(description="‰ dos aptos do cargo na UF (§2.3).")


class ListaCandidatos(BaseModel):
    """Página de candidatos."""

    total: int
    limite: int
    offset: int
    itens: list[CandidatoResumo]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total": 1,
                    "limite": 200,
                    "offset": 0,
                    "itens": [
                        {
                            "ano": 2026,
                            "sq_candidato": 3,
                            "nm_urna": "A",
                            "sg_uf": "SP",
                            "cargo": "DEPUTADO FEDERAL",
                            "partido": {"numero": 14, "sigla": "MISSÃO"},
                            "situacao": "APTO",
                            "resultado": "SUPLENTE",
                            "votos": 1000,
                            "pct_validos": 8.06,
                            "penetracao": 57.14,
                        }
                    ],
                }
            ]
        }
    )


def taxas(linhas: list[tuple[int, int, int]]) -> list[tuple[float | None, float | None]]:
    """(pct_validos, penetracao) de cada (votos, aptos, validos), pela biblioteca de indicadores."""
    quadro = pl.DataFrame(
        linhas, schema={"votos": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64}, orient="row"
    )
    calculado = desempenho.penetracao(desempenho.pct_validos(quadro))
    return list(zip(calculado["pct_validos"], calculado["penetracao"], strict=True))


def resumir(c: Candidatura, votos: int, bases: BasesPorEscopo) -> CandidatoResumo:
    """Resumo de um candidato com as taxas da circunscrição dele."""
    return _resumos([(c, votos)], bases)[0]


def _resumos(pares: list[tuple[Candidatura, int]], bases: BasesPorEscopo) -> list[CandidatoResumo]:
    """Resumos de vários candidatos com um único cálculo vetorizado das taxas."""
    entradas = [(votos, *bases.de(c)) for c, votos in pares]
    return [
        _montar_resumo(c, votos, pct, pen)
        for (c, votos), (pct, pen) in zip(pares, taxas(entradas), strict=True)
    ]


def _montar_resumo(
    c: Candidatura, votos: int, pct: float | None, pen: float | None
) -> CandidatoResumo:
    return CandidatoResumo(
        ano=c.ano,
        sq_candidato=c.sq_candidato,
        nm_urna=c.nm_urna,
        sg_uf=c.sg_uf,
        cargo=c.ds_cargo,
        partido=Partido(numero=c.nr_partido, sigla=c.sg_partido),
        situacao=c.ds_situacao_candidatura,
        resultado=c.ds_sit_tot_turno,
        votos=votos,
        pct_validos=pct,
        penetracao=pen,
    )


def listar_candidatos(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    grupo_id: str,
    uf: str | None,
    cargo: str | None,
    limite: int,
    offset: int,
) -> ListaCandidatos:
    """Candidatos do grupo ordenados por votos (desc) e nome."""
    grupo = catalogo.grupo(grupo_id)
    candidaturas = candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo)
    votos = repo.votos_totais(grupo.ano, [c.sq_candidato for c in candidaturas])
    bases = BasesPorEscopo(repo)
    itens = sorted(
        _resumos([(c, votos.get(c.sq_candidato, 0)) for c in candidaturas], bases),
        key=lambda i: (-i.votos, i.nm_urna, i.sq_candidato),
    )
    return ListaCandidatos(
        total=len(itens), limite=limite, offset=offset, itens=itens[offset : offset + limite]
    )


class VotosUF(BaseModel):
    """Votos do candidato numa UF."""

    uf: str
    votos: int


class VotosMunicipio(BaseModel):
    """Votos do candidato num município."""

    cd_mun_ibge: int
    nome: str
    uf: str
    votos: int
    penetracao: float | None = Field(description="‰ dos aptos do município no cargo.")


class FichaCandidato(BaseModel):
    """Ficha completa: votação, geografia e finanças."""

    candidato: CandidatoResumo
    votos_total: int
    votos_por_uf: list[VotosUF]
    votos_por_municipio: list[VotosMunicipio] = Field(description="Top N por votos.")
    gastos: ResumoCustoCandidato | None = Field(description="null se não há prestação de contas.")
    receitas: ResumoReceitasOut | None
    contas_parciais: bool = Field(description="Prestação de contas ainda parcial (2026).")
    base_ipca: str | None = Field(description="Mês-base da correção do IPCA (valores de 2022).")
    dt_geracao: str


def montar_ficha(repo: Repositorio, ano: int, sq_candidato: int, top: int) -> FichaCandidato:
    """Ficha do candidato; inexistente → 404."""
    c = repo.candidatura(ano, sq_candidato)
    if c is None:
        raise nao_encontrado("candidato_nao_encontrado", f"candidato {ano}/{sq_candidato}")
    por_mun = repo.votos_territorio(ano, [sq_candidato], por_zona=False)
    municipios = {m.cd_mun_ibge: m for m in repo.municipios([v.cd_mun_ibge for v in por_mun])}
    base = {
        b.cd_mun_ibge: b
        for b in repo.base_eleitoral(ano, c.ds_cargo, por_zona=False, uf=uf_da_base(c.sg_uf))
    }
    por_uf: dict[str, int] = {}
    quadro = desempenho.penetracao(
        pl.DataFrame(
            [
                (v.votos, base[v.cd_mun_ibge].aptos if v.cd_mun_ibge in base else None)
                for v in por_mun
            ],
            schema={"votos": pl.Int64, "aptos": pl.Int64},
            orient="row",
        )
    )
    linhas = []
    for v, pen in zip(por_mun, quadro["penetracao"], strict=True):
        m = municipios[v.cd_mun_ibge]
        por_uf[m.uf] = por_uf.get(m.uf, 0) + v.votos
        linhas.append(
            VotosMunicipio(
                cd_mun_ibge=m.cd_mun_ibge, nome=m.nome, uf=m.uf, votos=v.votos, penetracao=pen
            )
        )
    linhas.sort(key=lambda x: (-x.votos, x.cd_mun_ibge))
    votos_total = sum(v.votos for v in por_mun)
    contas = contas_de(repo, ano, [c])
    return FichaCandidato(
        candidato=resumir(c, votos_total, BasesPorEscopo(repo)),
        votos_total=votos_total,
        votos_por_uf=[VotosUF(uf=u, votos=n) for u, n in sorted(por_uf.items())],
        votos_por_municipio=linhas[:top],
        gastos=contas.por_candidato[0].custo if contas.por_candidato else None,
        receitas=contas.receitas if contas.por_candidato else None,
        contas_parciais=contas.parcial,
        base_ipca=contas.base_ipca,
        dt_geracao=repo.dt_geracao(),
    )
