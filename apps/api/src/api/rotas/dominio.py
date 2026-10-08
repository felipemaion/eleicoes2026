"""Rotas de domínio: HTTP fino (validação + chamada ao serviço); regra fica nos serviços."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from api.deps import CacheDep, CatalogoDep, RepositorioDep
from api.dominio import UF, Ano, Cargo, Indicador, Nivel
from api.servicos.candidatos import FichaCandidato, ListaCandidatos, listar_candidatos, montar_ficha
from api.servicos.comparativo import Comparativo, montar_comparativo
from api.servicos.gastos import Gastos, montar_gastos
from api.servicos.grupos import GruposResposta, listar_grupos
from api.servicos.mapa import Mapa, Pontos, montar_mapa, montar_pontos
from api.servicos.municipio import ResumoMunicipio, montar_resumo

router = APIRouter()

GrupoQ = Annotated[str, Query(description="Id do grupo em config/grupos.yaml (ex.: missao_2026).")]
GrupoOpcional = Annotated[str | None, Query(description="Id do grupo; exclusivo com sq_candidato.")]
SqOpcional = Annotated[int | None, Query(description="SQ_CANDIDATO; exclusivo com grupo.")]


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
    uf_v, cargo_v = (uf.value if uf else None), (cargo.value if cargo else None)
    return cache.obter(
        repo.dt_geracao(),
        ("candidatos", grupo, uf_v, cargo_v, limite, offset),
        lambda: listar_candidatos(
            repo, catalogo, grupo_id=grupo, uf=uf_v, cargo=cargo_v, limite=limite, offset=offset
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
    cache: CacheDep,
    ano: Ano,
    sq_candidato: int,
    top: Annotated[int, Query(ge=1, le=100, description="Municípios no ranking.")] = 10,
) -> FichaCandidato:
    """Votos por UF e município (top N), gastos, receitas por fonte e custo por voto."""
    return cache.obter(
        repo.dt_geracao(),
        ("ficha", ano, sq_candidato, top),
        lambda: montar_ficha(repo, ano.value, sq_candidato, top),
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
    uf: UF,
    grupo: GrupoOpcional = None,
    sq_candidato: SqOpcional = None,
    limite: Annotated[int, Query(ge=1, le=50000)] = 5000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pontos:
    """`{lat, lon, votos}` por local, mais votados primeiro; paginado por UF."""
    return cache.obter(
        repo.dt_geracao(),
        ("pontos", ano, cargo, uf, grupo, sq_candidato, limite, offset),
        lambda: montar_pontos(
            repo,
            catalogo,
            ano=ano.value,
            cargo=cargo.value,
            uf=uf.value,
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
    uf_v, cargo_v = (uf.value if uf else None), (cargo.value if cargo else None)
    return cache.obter(
        repo.dt_geracao(),
        ("gastos", grupo, uf_v, cargo_v),
        lambda: montar_gastos(repo, catalogo, grupo_id=grupo, uf=uf_v, cargo=cargo_v),
    )


@router.get(
    "/comparativo", response_model=Comparativo, tags=["comparativo"], summary="Evolução 2022→2026"
)
def comparativo(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    comparacao: Annotated[str, Query(description="Id em `comparacoes` (ex.: evolucao_mbl).")],
    cargo: Cargo,
    uf: UF | None = None,
    mesmos_candidatos: Annotated[
        bool, Query(description="Só pessoas que concorreram nos dois anos (pessoa_id).")
    ] = False,
) -> Comparativo:
    """Δ penetração (‰), swing (p.p.), retenção e ganho por AMC, mais KPIs do recorte."""
    uf_v = uf.value if uf else None
    return cache.obter(
        repo.dt_geracao(),
        ("comparativo", comparacao, cargo, uf_v, mesmos_candidatos),
        lambda: montar_comparativo(
            repo,
            catalogo,
            comparacao_id=comparacao,
            cargo=cargo,
            uf=uf_v,
            mesmos_candidatos=mesmos_candidatos,
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
