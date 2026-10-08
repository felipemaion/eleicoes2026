"""Rotas de redes sociais: HTTP fino; a regra vive em `servicos/redes*.py`."""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import StringConstraints

from api.deps import CacheDep, CatalogoDep, RepositorioDep
from api.dominio import UF, Cargo
from api.servicos.redes import Redes, montar_redes
from api.servicos.redes_correlacoes import (
    Correlacoes,
    SerieRedes,
    montar_correlacoes,
    montar_serie,
)

router = APIRouter(prefix="/redes", tags=["redes"])

GrupoQ = Annotated[str, Query(description="Id do grupo em config/grupos.yaml (só 2026).")]
Username = Annotated[str, StringConstraints(pattern=r"^[a-z0-9._]{1,30}$")]
_ERRO_REDES: dict[int | str, dict[str, Any]] = {
    503: {"description": "Dados de redes sociais ainda não publicados."}
}


@router.get(
    "",
    response_model=Redes,
    summary="Instagram dos candidatos do grupo",
    responses={422: {"description": "Grupo de outro ano ou desconhecido."}, **_ERRO_REDES},
)
def redes(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    grupo: GrupoQ,
    uf: UF | None = None,
    cargo: Cargo | None = None,
) -> Redes:
    """Perfis, seguidores, ritmo de posts, engajamento e seguidores por mil votos.

    Perfil indisponível (conta pessoal ou inexistente) volta com campos nulos e `status`: nunca
    zero. `excluidos` conta quem fica fora das médias e correlações, por motivo.
    """
    uf_v, cargo_v = (uf.value if uf else None), (cargo.value if cargo else None)
    return cache.obter(
        repo.versao_dados(),
        ("redes", grupo, uf_v, cargo_v),
        lambda: montar_redes(repo, catalogo, grupo_id=grupo, uf=uf_v, cargo=cargo_v),
    )


@router.get(
    "/correlacoes",
    response_model=Correlacoes,
    summary="Correlação entre redes e votos",
    responses={422: {"description": "Grupo de outro ano ou desconhecido."}, **_ERRO_REDES},
)
def correlacoes(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    grupo: GrupoQ,
    uf: UF | None = None,
    cargo: Cargo | None = None,
    por_uf: Annotated[
        bool, Query(description="Uma correlação por cargo × UF (deputados de UFs diferentes).")
    ] = False,
) -> Correlacoes:
    """ρ de Spearman (IC 95 % bootstrap, n, exclusões) e nuvem seguidores × votos por cargo.

    Descritivo: correlação não é causalidade. Com menos de 10 candidatos o ρ vem nulo.
    """
    uf_v, cargo_v = (uf.value if uf else None), (cargo.value if cargo else None)
    return cache.obter(
        repo.versao_dados(),
        ("redes_correlacoes", grupo, uf_v, cargo_v, por_uf),
        lambda: montar_correlacoes(
            repo, catalogo, grupo_id=grupo, uf=uf_v, cargo=cargo_v, por_uf=por_uf
        ),
    )


@router.get(
    "/serie",
    response_model=SerieRedes,
    summary="Série de seguidores no tempo",
    responses={
        404: {"description": "Candidato inexistente ou sem nenhuma coleta com seguidores."},
        422: {"description": "Informe exatamente um entre `sq` e `username`."},
        **_ERRO_REDES,
    },
)
def serie(
    repo: RepositorioDep,
    cache: CacheDep,
    sq: Annotated[
        int | None, Query(description="SQ_CANDIDATO (2026); exclusivo com username.")
    ] = None,
    username: Annotated[
        Username | None, Query(description="Perfil do Instagram; exclusivo com sq.")
    ] = None,
) -> SerieRedes:
    """Seguidores a cada coleta, desde a primeira (08/10/2026); nunca interpola o passado."""
    return cache.obter(
        repo.versao_dados(),
        ("redes_serie", sq, username),
        lambda: montar_serie(repo, sq=sq, username=username),
    )
