"""Casos de uso /candidatos e /candidatos/{ano}/{sq}."""

from collections import Counter
from typing import Literal

import polars as pl
from indicadores import desempenho
from indicadores.grupos import agregar_grupo
from pydantic import BaseModel, ConfigDict, Field

from api.erros import nao_encontrado, parametro_invalido
from api.fontes import Fonte, fontes
from api.fotos import ComFotoELink, foto_e_link
from api.links import Link, links_da_candidatura
from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.contas import (
    ContasCand,
    ResumoCustoCandidato,
    ResumoReceitasOut,
    contas_de,
)
from api.servicos.escopo import BasesPorEscopo, uf_da_base
from api.servicos.grupos import Catalogo, DefinicaoGrupo, candidaturas_do_grupo


class Partido(BaseModel):
    """Partido da candidatura."""

    numero: int
    sigla: str


class Abrangencia(BaseModel):
    """Região em que o candidato disputa: o front enquadra o mapa por ela."""

    tipo: Literal["pais", "uf"] = Field(description="`pais` (presidente) ou `uf`.")
    uf: str | None = Field(description="Sigla da UF; null quando `tipo = pais`.")


def abrangencia_de(c: Candidatura) -> Abrangencia:
    """Presidente (gravado com `sg_uf = BR`) → país; os demais cargos → a UF da candidatura."""
    return (
        Abrangencia(tipo="pais", uf=None) if c.sg_uf == "BR" else Abrangencia(tipo="uf", uf=c.sg_uf)
    )


class CandidatoResumo(ComFotoELink):
    """Candidato com votos e taxas na sua circunscrição (cargo × UF)."""

    ano: int
    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    partido: Partido
    situacao: str | None = Field(
        description="`ds_situacao_candidatura` (APTO, INDEFERIDO…); null = TSE ainda não publicou."
    )
    resultado: str | None = Field(
        description="`ds_sit_tot_turno` (ELEITO, SUPLENTE…); null se sem apuração."
    )
    votos: int = Field(description="Votos nominais válidos (spec §2.1).")
    pct_validos: float | None = Field(description="% dos válidos do cargo na UF (§2.2).")
    penetracao: float | None = Field(description="‰ dos aptos do cargo na UF (§2.3).")
    indicado: bool = Field(
        description="Candidatura indicada pelo grupo (`origem=indicado` na lista de referência); "
        "false para candidatos próprios ou fora da lista."
    )
    abrangencia: Abrangencia


class KpisGrupo(BaseModel):
    """Grupo como candidato coletivo no recorte (cargo × UF): soma única, nunca de cargos."""

    votos: int = Field(description="Σ votos nominais válidos dos membros (spec §2.1).")
    aptos: int = Field(description="Aptos do cargo no recorte (denominador da penetração).")
    validos: int = Field(description="Votos válidos do cargo no recorte (denominador do %).")
    pct_validos: float | None = Field(description="% dos válidos do cargo (§2.2).")
    penetracao: float | None = Field(description="‰ dos aptos do cargo (§2.3).")


class ListaCandidatos(BaseModel):
    """Página de candidatos."""

    total: int
    limite: int
    offset: int
    itens: list[CandidatoResumo]
    kpis: KpisGrupo | None = Field(
        description="Indicadores do grupo inteiro no recorte; null sem `cargo` (não se somam "
        "cargos) ou sem candidaturas."
    )
    fontes: list[Fonte] = Field(description="Procedência dos números (arquivo, regra, spec).")

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
                            "indicado": False,
                            "abrangencia": {"tipo": "uf", "uf": "SP"},
                        }
                    ],
                    "kpis": {
                        "votos": 1000,
                        "aptos": 17500,
                        "validos": 12400,
                        "pct_validos": 8.06,
                        "penetracao": 57.14,
                    },
                    "fontes": [
                        {
                            "dataset": "votacao_candidato_munzona",
                            "arquivo_oficial_url": "https://cdn.tse.jus.br/estatistica/sead/odsele/"
                            "votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
                            "dt_geracao": "2026-10-06",
                            "coluna_regra": "QT_VOTOS_NOMINAIS_VALIDOS com destinação 'Válido'.",
                            "metodologia_url": "https://github.com/felipemaion/eleicoes2026/blob/"
                            "main/docs/metodologia/indicadores.md#21-votos-nominais",
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


def resumir(
    c: Candidatura,
    votos: int,
    bases: BasesPorEscopo,
    indicados: frozenset[int],
    fotos: frozenset[tuple[int, int]],
) -> CandidatoResumo:
    """Resumo de um candidato com as taxas da circunscrição dele."""
    return _resumos([(c, votos)], bases, indicados, fotos)[0]


def _resumos(
    pares: list[tuple[Candidatura, int]],
    bases: BasesPorEscopo,
    indicados: frozenset[int],
    fotos: frozenset[tuple[int, int]],
) -> list[CandidatoResumo]:
    """Resumos de vários candidatos com um único cálculo vetorizado das taxas."""
    entradas = [(votos, *bases.de(c)) for c, votos in pares]
    return [
        _montar_resumo(c, votos, pct, pen, c.sq_candidato in indicados, fotos)
        for (c, votos), (pct, pen) in zip(pares, taxas(entradas), strict=True)
    ]


def _montar_resumo(
    c: Candidatura,
    votos: int,
    pct: float | None,
    pen: float | None,
    indicado: bool,
    fotos: frozenset[tuple[int, int]],
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
        indicado=indicado,
        abrangencia=abrangencia_de(c),
        **foto_e_link(fotos, ano=c.ano, sq_candidato=c.sq_candidato, uf=c.sg_uf),
    )


def kpis_do_grupo(
    repo: Repositorio,
    grupo: DefinicaoGrupo,
    candidaturas: list[Candidatura],
    *,
    cargo: str,
    uf: str | None,
) -> KpisGrupo | None:
    """Indicadores do grupo como candidato coletivo (`agregar_grupo`), no cargo e UF pedidos."""
    if not candidaturas:
        return None
    sqs = [c.sq_candidato for c in candidaturas]
    todos = repo.votos_territorio(grupo.ano, sqs, por_zona=False, uf=uf)
    # Exterior (sem município IBGE) soma ao total do grupo mas não entra por município.
    exterior = sum(v.votos for v in todos if v.cd_mun_ibge is None)
    por_mun = [v for v in todos if v.cd_mun_ibge is not None]
    # `votos_territorio` já devolve Σ dos membros por município; o quadro leva o grupo como
    # entidade única para que `agregar_grupo` imponha cargo/turno únicos e some por município.
    votos = pl.DataFrame(
        {
            "grupo": [grupo.id] * len(por_mun),
            "cd_mun_ibge": [v.cd_mun_ibge for v in por_mun],
            "votos": [v.votos for v in por_mun],
        },
        schema={"grupo": pl.String, "cd_mun_ibge": pl.Int64, "votos": pl.Int64},
    )
    total = exterior
    if not votos.is_empty():
        total += int(agregar_grupo(votos, [grupo.id], grupo.id, entidade="grupo")["votos"].sum())
    base = repo.base_eleitoral(grupo.ano, cargo, por_zona=False, uf=uf)
    aptos, validos = sum(b.aptos for b in base), sum(b.validos for b in base)
    ((pct, pen),) = taxas([(total, aptos, validos)])
    return KpisGrupo(votos=total, aptos=aptos, validos=validos, pct_validos=pct, penetracao=pen)


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
        _resumos(
            [(c, votos.get(c.sq_candidato, 0)) for c in candidaturas],
            bases,
            catalogo.indicados,
            repo.fotos(),
        ),
        key=lambda i: (-i.votos, i.nm_urna, i.sq_candidato),
    )
    return ListaCandidatos(
        total=len(itens),
        limite=limite,
        offset=offset,
        itens=itens[offset : offset + limite],
        kpis=kpis_do_grupo(repo, grupo, candidaturas, cargo=cargo, uf=uf) if cargo else None,
        fontes=fontes(
            ["votacao_candidato_munzona", "detalhe_votacao_munzona"],
            ano=grupo.ano,
            dt_geracao=repo.dt_geracao(),
        ),
    )


UF_EXTERIOR = "ZZ"  # sigla do TSE para votos no exterior


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


class GastosCandidato(ResumoCustoCandidato):
    """Finanças da campanha: despesa, repasses, receita e custo por voto com e sem repasses."""

    repasses_contratados: float = Field(
        description="R$ contratados como doação a outros candidatos/partidos (fora do custo)."
    )
    repasses_pagos: float = Field(description="R$ pagos nesses repasses.")
    despesa_total_contratada: float = Field(
        description="Despesa própria + repasses (contratada): tudo que a campanha comprometeu."
    )
    despesa_total_paga: float = Field(description="Despesa própria + repasses (paga).")
    custo_voto_contratado_com_repasses: float | None = Field(
        description="despesa total contratada ÷ votos. Maior ou igual ao custo sem repasses: a "
        "diferença é o dinheiro repassado a terceiros. null se votos = 0."
    )
    custo_voto_pago_com_repasses: float | None
    receita_total: float = Field(description="Σ das receitas da campanha (todas as fontes).")
    receita_por_fonte: dict[str, float] = Field(
        description="Receita por categoria (§4.1): fefc, fundo_partidario, recursos_proprios…"
    )
    receita_por_voto: float | None = Field(description="R$/voto = receita ÷ votos (§4.7).")
    receita_por_mil_aptos: float | None = Field(description="R$ por mil aptos da circunscrição.")
    saldo_contratado: float | None = Field(
        description="receita − despesa contratada, com repasses (§4.8)."
    )
    saldo_financeiro: float | None = Field(description="receita financeira − despesa paga.")
    pct_receita_gasta: float | None = Field(description="100 × despesa contratada ÷ receita.")
    explicacao_repasses: str = Field(
        description="Por que há dois custos por voto e qual a diferença entre eles."
    )


EXPLICACAO_REPASSES = (
    "O custo por voto principal exclui repasses (doações financeiras a outros candidatos ou "
    "partidos), porque esse dinheiro não comprou voto para este candidato (spec §4.2). A versão "
    "com repasses divide a despesa total — própria + repasses — pelos mesmos votos."
)


def _gastos_da_ficha(cc: ContasCand, receitas: ResumoReceitasOut) -> GastosCandidato:
    """Monta as finanças da ficha; só soma e divide valores já calculados pela lib."""
    c = cc.custo
    total_c = c.despesa_contratada + cc.repasses_contratados
    total_p = c.despesa_paga + cc.repasses_pagos
    return GastosCandidato(
        **c.model_dump(),
        repasses_contratados=cc.repasses_contratados,
        repasses_pagos=cc.repasses_pagos,
        despesa_total_contratada=total_c,
        despesa_total_paga=total_p,
        custo_voto_contratado_com_repasses=total_c / c.votos if c.votos else None,
        custo_voto_pago_com_repasses=total_p / c.votos if c.votos else None,
        receita_total=receitas.receita_total,
        receita_por_fonte=receitas.por_categoria,
        receita_por_voto=cc.receita_por_voto,
        receita_por_mil_aptos=cc.receita_por_mil_aptos,
        saldo_contratado=cc.saldo_contratado,
        saldo_financeiro=cc.saldo_financeiro,
        pct_receita_gasta=cc.pct_receita_gasta,
        explicacao_repasses=EXPLICACAO_REPASSES,
    )


class FichaCandidato(BaseModel):
    """Ficha completa: votação, geografia e finanças."""

    candidato: CandidatoResumo
    votos_total: int
    votos_por_uf: list[VotosUF]
    votos_por_municipio: list[VotosMunicipio] = Field(description="Top N por votos.")
    gastos: GastosCandidato | None = Field(description="null se não há prestação de contas.")
    receitas: ResumoReceitasOut | None
    contas_parciais: bool = Field(description="Prestação de contas ainda parcial (2026).")
    base_ipca: str | None = Field(description="Mês-base da correção do IPCA (valores de 2022).")
    dt_geracao: str
    links: list[Link] = Field(
        description="Links oficiais do TSE (votos, perfil, contas, dados abertos); cada um diz "
        "se foi `verificado` e, se não, o que conferir."
    )
    fontes: list[Fonte] = Field(description="Procedência dos números da ficha.")


def montar_ficha(
    repo: Repositorio, catalogo: Catalogo, ano: int, sq_candidato: int, top: int
) -> FichaCandidato:
    """Ficha do candidato; inexistente → 404."""
    c = repo.candidatura(ano, sq_candidato)
    if c is None:
        raise nao_encontrado("candidato_nao_encontrado", f"candidato {ano}/{sq_candidato}")
    todos = repo.votos_territorio(ano, [sq_candidato], por_zona=False)
    # Voto sem município (exterior) entra no total e em `ZZ`, mas não tem município nem taxa.
    exterior = sum(v.votos for v in todos if v.cd_mun_ibge is None)
    por_mun = [(v.cd_mun_ibge, v.votos) for v in todos if v.cd_mun_ibge is not None]
    municipios = {m.cd_mun_ibge: m for m in repo.municipios([cd for cd, _ in por_mun])}
    if any(cd not in municipios for cd, _ in por_mun):
        raise DadosIndisponiveis("voto em município fora do cadastro (municipio_tse_ibge)")
    base = {
        b.cd_mun_ibge: b
        for b in repo.base_eleitoral(ano, c.ds_cargo, por_zona=False, uf=uf_da_base(c.sg_uf))
    }
    por_uf: dict[str, int] = {}
    quadro = desempenho.penetracao(
        pl.DataFrame(
            [(votos, base[cd].aptos if cd in base else None) for cd, votos in por_mun],
            schema={"votos": pl.Int64, "aptos": pl.Int64},
            orient="row",
        )
    )
    linhas = []
    for (cd, votos), pen in zip(por_mun, quadro["penetracao"], strict=True):
        m = municipios[cd]
        por_uf[m.uf] = por_uf.get(m.uf, 0) + votos
        linhas.append(
            VotosMunicipio(
                cd_mun_ibge=m.cd_mun_ibge, nome=m.nome, uf=m.uf, votos=votos, penetracao=pen
            )
        )
    linhas.sort(key=lambda x: (-x.votos, x.cd_mun_ibge))
    if exterior:
        por_uf[UF_EXTERIOR] = exterior
    votos_total = sum(votos for _, votos in por_mun) + exterior
    contas = contas_de(repo, ano, [c])
    return FichaCandidato(
        candidato=resumir(c, votos_total, BasesPorEscopo(repo), catalogo.indicados, repo.fotos()),
        votos_total=votos_total,
        votos_por_uf=[VotosUF(uf=u, votos=n) for u, n in sorted(por_uf.items())],
        votos_por_municipio=linhas[:top],
        gastos=_gastos_da_ficha(contas.por_candidato[0], contas.receitas)
        if contas.por_candidato
        else None,
        receitas=contas.receitas if contas.por_candidato else None,
        contas_parciais=contas.parcial,
        base_ipca=contas.base_ipca,
        dt_geracao=repo.dt_geracao(),
        links=links_da_candidatura(
            ano=ano, sq_candidato=sq_candidato, uf=c.sg_uf, cargo=c.ds_cargo
        ),
        fontes=fontes(
            ["consulta_cand", "votacao_candidato_munzona", "detalhe_votacao_munzona"]
            + (["prestacao_contas"] if contas.por_candidato else [])
            + (["ipca"] if contas.base_ipca else []),
            ano=ano,
            dt_geracao=repo.dt_geracao(),
        ),
    )


class UfDisponivel(BaseModel):
    """UF com candidaturas no recorte."""

    uf: str = Field(description="Sigla da UF; `BR` para presidente (candidatura nacional).")
    candidaturas: int = Field(description="Candidaturas do recorte nessa UF.")


class UfsDisponiveis(BaseModel):
    """Corpo de GET /candidatos/ufs."""

    itens: list[UfDisponivel]
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"itens": [{"uf": "BR", "candidaturas": 1}], "dt_geracao": "2026-10-06"}]
        }
    )


def ufs_disponiveis(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int | None,
    cargo: str | None,
    grupo_id: str | None,
) -> UfsDisponiveis:
    """UFs que têm candidatura no recorte (ano ou grupo, cargo), em ordem alfabética.

    Alimenta o seletor de UF do frontend: só aparece o que existe (presidente → `BR`).
    """
    if grupo_id is None:
        if ano is None:
            raise parametro_invalido("recorte_incompleto", "informe 'ano' ou 'grupo'")
        achadas = repo.candidaturas(ano, cargo=cargo)
    else:
        grupo = catalogo.grupo(grupo_id)
        if ano is not None and ano != grupo.ano:
            raise parametro_invalido(
                "grupo_ano_incompativel", f"o grupo '{grupo_id}' é de {grupo.ano}, não de {ano}"
            )
        achadas = candidaturas_do_grupo(repo, grupo, cargo=cargo)
    contagem = Counter(c.sg_uf for c in achadas)
    return UfsDisponiveis(
        itens=[UfDisponivel(uf=u, candidaturas=n) for u, n in sorted(contagem.items())],
        dt_geracao=repo.dt_geracao(),
    )
