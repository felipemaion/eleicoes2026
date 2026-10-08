"""Rotas de domínio: HTTP fino (validação + chamada ao serviço); regra fica nos serviços."""

from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import StringConstraints

from api.deps import CacheDep, CatalogoDep, RepositorioDep
from api.dominio import UF, Ano, Cargo, Indicador, Nivel
from api.servicos.busca import ListaPessoas, ResultadoBusca, buscar, listar_pessoas
from api.servicos.candidatos import (
    FichaCandidato,
    ListaCandidatos,
    UfsDisponiveis,
    montar_ficha,
    ufs_disponiveis,
)
from api.servicos.comparativo import Comparativo
from api.servicos.consultas import candidatos_em_cache, comparativo_em_cache, gastos_em_cache
from api.servicos.gastos import Gastos
from api.servicos.grupos import GruposResposta, listar_grupos
from api.servicos.mapa import Mapa, Pontos, montar_mapa, montar_pontos
from api.servicos.municipio import ResumoMunicipio, montar_resumo

router = APIRouter()

GrupoQ = Annotated[str, Query(description="Id do grupo em config/grupos.yaml (ex.: missao_2026).")]
GrupoOpcional = Annotated[str | None, Query(description="Id do grupo; exclusivo com sq_candidato.")]
SqOpcional = Annotated[int | None, Query(description="SQ_CANDIDATO; exclusivo com grupo.")]
IdPublico = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")]
MAX_SELECAO = 50  # candidaturas/pessoas por seleção: limita o custo da consulta


@router.get(
    "/grupos", response_model=GruposResposta, tags=["grupos"], summary="Grupos e comparações"
)
def grupos(repo: RepositorioDep, catalogo: CatalogoDep) -> GruposResposta:
    """Grupos configurados (com nº de candidaturas nos dados) e comparações entre eles."""
    return listar_grupos(repo, catalogo)


@router.get(
    "/candidatos",
    response_model=ListaCandidatos,
    tags=["candidatos"],
    summary="Candidatos de um grupo",
)
def candidatos(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    grupo: GrupoQ,
    uf: UF | None = None,
    cargo: Cargo | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListaCandidatos:
    """Votos, % dos válidos, penetração, resultado e partido, ordenados por votos."""
    return candidatos_em_cache(
        repo,
        catalogo,
        cache,
        grupo=grupo,
        uf=uf.value if uf else None,
        cargo=cargo.value if cargo else None,
        limite=limite,
        offset=offset,
    )


@router.get(
    "/candidatos/ufs",
    response_model=UfsDisponiveis,
    tags=["candidatos"],
    summary="UFs com candidaturas",
)
def candidatos_ufs(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    ano: Ano | None = None,
    cargo: Cargo | None = None,
    grupo: GrupoOpcional = None,
) -> UfsDisponiveis:
    """UFs com candidaturas no recorte (`ano` ou `grupo`, mais `cargo`), com contagem.

    Presidente devolve só `BR`. Exige `ano` ou `grupo`; o grupo define o ano.
    """
    return cache.obter(
        repo.dt_geracao(),
        ("candidatos_ufs", ano, cargo, grupo),
        lambda: ufs_disponiveis(
            repo,
            catalogo,
            ano=ano.value if ano else None,
            cargo=cargo.value if cargo else None,
            grupo_id=grupo,
        ),
    )


@router.get(
    "/candidatos/{ano}/{sq_candidato}",
    response_model=FichaCandidato,
    tags=["candidatos"],
    summary="Ficha do candidato",
    responses={404: {"description": "Candidato inexistente."}},
)
def ficha(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    ano: Ano,
    sq_candidato: int,
    top: Annotated[int, Query(ge=1, le=100, description="Municípios no ranking.")] = 10,
) -> FichaCandidato:
    """Votos por UF e município (top N), gastos, receitas por fonte e custo por voto."""
    return cache.obter(
        repo.dt_geracao(),
        ("ficha", ano, sq_candidato, top),
        lambda: montar_ficha(repo, catalogo, ano.value, sq_candidato, top),
    )


@router.get("/mapa", response_model=Mapa, tags=["mapa"], summary="Indicador por território")
def mapa(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    ano: Ano,
    cargo: Cargo,
    uf: UF | None = None,
    nivel: Nivel = Nivel.MUNICIPIO,
    grupo: GrupoOpcional = None,
    sq_candidato: SqOpcional = None,
    indicador: Indicador = Indicador.PENETRACAO,
    comparacao: Annotated[
        str | None,
        Query(
            description="Id em `comparacoes`: a escala usa quebras comuns aos dois anos "
            "(exige `grupo` = um dos lados)."
        ),
    ] = None,
) -> Mapa:
    """`valores` por território (município, `município-zona` ou célula H3) + escala sugerida."""
    uf_v = uf.value if uf else None
    return cache.obter(
        repo.dt_geracao(),
        ("mapa", ano, cargo, uf_v, nivel, indicador, grupo, sq_candidato, comparacao),
        lambda: montar_mapa(
            repo,
            catalogo,
            ano=ano.value,
            cargo=cargo.value,
            uf=uf_v,
            nivel=nivel,
            indicador=indicador,
            grupo_id=grupo,
            sq_candidato=sq_candidato,
            comparacao=comparacao,
        ),
    )


@router.get(
    "/mapa/pontos", response_model=Pontos, tags=["mapa"], summary="Locais de votação (densidade)"
)
def pontos(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    ano: Ano,
    cargo: Cargo,
    uf: Annotated[
        UF | None,
        Query(description="Sem UF (Brasil, ex.: presidente): locais somados em células de 0,1°."),
    ] = None,
    grupo: GrupoOpcional = None,
    sq_candidato: SqOpcional = None,
    limite: Annotated[int, Query(ge=1, le=50000)] = 5000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pontos:
    """`{lat, lon, votos}` por local, mais votados primeiro; paginado."""
    uf_v = uf.value if uf else None
    return cache.obter(
        repo.dt_geracao(),
        ("pontos", ano, cargo, uf_v, grupo, sq_candidato, limite, offset),
        lambda: montar_pontos(
            repo,
            catalogo,
            ano=ano.value,
            cargo=cargo.value,
            uf=uf_v,
            grupo_id=grupo,
            sq_candidato=sq_candidato,
            limite=limite,
            offset=offset,
        ),
    )


@router.get("/gastos", response_model=Gastos, tags=["gastos"], summary="Gastos e receitas do grupo")
def gastos(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    grupo: GrupoQ,
    uf: UF | None = None,
    cargo: Cargo | None = None,
) -> Gastos:
    """Custo por voto (contratado/pago), receita por fonte, % público e % autofinanciamento."""
    return gastos_em_cache(
        repo,
        catalogo,
        cache,
        grupo=grupo,
        uf=uf.value if uf else None,
        cargo=cargo.value if cargo else None,
    )


@router.get(
    "/comparativo", response_model=Comparativo, tags=["comparativo"], summary="Evolução 2022→2026"
)
def comparativo(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    cargo: Cargo,
    comparacao: Annotated[
        str | None, Query(description="Id em `comparacoes` (ex.: evolucao_mbl).")
    ] = None,
    uf: UF | None = None,
    mesmos_candidatos: Annotated[
        bool, Query(description="Só pessoas que concorreram nos dois anos (pessoa_id).")
    ] = False,
    pessoas: Annotated[
        list[IdPublico] | None,
        Query(
            max_length=MAX_SELECAO,
            description="Seleção do usuário: `pessoa_id_publico` (de /busca ou /evolucao/pessoas); "
            "compara as candidaturas delas em 2022 e 2026. Exclusivo com `comparacao`.",
        ),
    ] = None,
    sq_2022: Annotated[
        list[int] | None,
        Query(max_length=MAX_SELECAO, description="Seleção: `sq_candidato` de 2022."),
    ] = None,
    sq_2026: Annotated[
        list[int] | None,
        Query(max_length=MAX_SELECAO, description="Seleção: `sq_candidato` de 2026."),
    ] = None,
    grupo_2022: Annotated[
        str | None,
        Query(description="Lado 2022 = grupo (id de 2022 em /grupos). Exclusivo com `sq_2022`."),
    ] = None,
    grupo_2026: Annotated[
        str | None,
        Query(description="Lado 2026 = grupo (id de 2026 em /grupos). Exclusivo com `sq_2026`."),
    ] = None,
) -> Comparativo:
    """Δ penetração (‰), swing (p.p.), retenção e ganho por AMC, mais KPIs do recorte.

    Ou `comparacao` (atalho para um par de grupos), ou um valor por lado, combináveis:
    `grupo_2022`/`sq_2022` × `grupo_2026`/`sq_2026` (ou `pessoas`, que preenche os dois lados).
    Lado sem grupo nem candidatos → 422 `lado_vazio`; grupo e candidatos no mesmo lado →
    `lado_ambiguo`; grupo do ano errado → `grupo_ano_errado`; `comparacao` com lados →
    `comparacao_e_selecao`; sem candidaturas no cargo/UF → `sem_par_comparavel`.
    """
    return comparativo_em_cache(
        repo,
        catalogo,
        cache,
        comparacao=comparacao,
        cargo=cargo,
        uf=uf.value if uf else None,
        mesmos_candidatos=mesmos_candidatos,
        pessoas=pessoas or (),
        sq_2022=sq_2022 or (),
        sq_2026=sq_2026 or (),
        grupo_2022=grupo_2022,
        grupo_2026=grupo_2026,
    )


@router.get(
    "/busca",
    response_model=ResultadoBusca,
    tags=["busca"],
    summary="Busca de candidaturas",
)
def busca(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=80,
            description="Nome de urna ou civil (sem acento, qualquer caixa; início de palavra "
            "antes de trecho), número de urna (prefixo), número ou sigla do partido.",
        ),
    ],
    ano: Ano | None = None,
    cargo: Cargo | None = None,
    uf: UF | None = None,
    grupo: GrupoOpcional = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResultadoBusca:
    """Candidaturas com ano, cargo, UF, partido, votos, resultado e `abrangencia` do mapa."""
    return cache.obter(
        repo.dt_geracao(),
        ("busca", q, ano, cargo, uf, grupo, limite),
        lambda: buscar(
            repo,
            catalogo,
            q=q,
            ano=ano.value if ano else None,
            cargo=cargo.value if cargo else None,
            uf=uf.value if uf else None,
            grupo_id=grupo,
            limite=limite,
        ),
    )


@router.get(
    "/evolucao/pessoas",
    response_model=ListaPessoas,
    tags=["comparativo"],
    summary="Pessoas em 2022 e 2026",
)
def evolucao_pessoas(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    q: Annotated[
        str | None, Query(max_length=80, description="Nome (urna ou civil), como em /busca.")
    ] = None,
    uf: UF | None = None,
    cargo: Annotated[Cargo | None, Query(description="Exige este cargo nos dois anos.")] = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    pessoas: Annotated[
        list[IdPublico] | None,
        Query(
            max_length=MAX_SELECAO,
            description="`pessoa_id_publico` que devem vir na resposta mesmo fora da página "
            "(`limite`) do recorte.",
        ),
    ] = None,
) -> ListaPessoas:
    """Quem concorreu nos dois anos, com o resumo de cada ano; alimenta `/comparativo?pessoas=`."""
    return cache.obter(
        repo.dt_geracao(),
        ("evolucao_pessoas", q, uf, cargo, limite, tuple(pessoas or ())),
        lambda: listar_pessoas(
            repo,
            catalogo,
            q=q,
            uf=uf.value if uf else None,
            cargo=cargo.value if cargo else None,
            limite=limite,
            pessoas=pessoas or (),
        ),
    )


@router.get(
    "/municipios/{cd_mun_ibge}",
    response_model=ResumoMunicipio,
    tags=["municipios"],
    summary="Resumo do município",
    responses={404: {"description": "Município inexistente."}},
)
def municipio(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    cd_mun_ibge: Annotated[str, Path(pattern=r"^\d{7}$", description="Código IBGE de 7 dígitos.")],
) -> ResumoMunicipio:
    """Desempenho de cada grupo no município, por cargo."""
    return cache.obter(
        repo.dt_geracao(),
        ("municipio", cd_mun_ibge),
        lambda: montar_resumo(repo, catalogo, int(cd_mun_ibge)),
    )
