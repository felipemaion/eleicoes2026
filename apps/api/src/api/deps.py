"""Dependências injetadas (FastAPI Depends); nada de globais."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from api.cache_servico import CacheLRU
from api.repositorio.base import Repositorio
from api.servicos.grupos import Catalogo
from api.servicos.meta import Grupo

_INDISPONIVEL = HTTPException(status_code=503, detail={"codigo": "dados_indisponiveis"})


def obter_repositorio(request: Request) -> Repositorio:
    """Repositório aberto no lifespan; 503 se os dados não abriram."""
    repo: Repositorio | None = request.app.state.repositorio
    if repo is None:
        raise _INDISPONIVEL
    return repo


def obter_grupos(request: Request) -> list[Grupo]:
    """Grupos carregados no lifespan."""
    grupos: list[Grupo] = request.app.state.grupos
    return grupos


def obter_catalogo(request: Request) -> Catalogo:
    """Catálogo de grupos/comparações carregado no lifespan."""
    catalogo: Catalogo = request.app.state.catalogo
    return catalogo


def obter_cache(request: Request) -> CacheLRU:
    """Cache de resultados dos serviços (um por processo)."""
    cache: CacheLRU = request.app.state.cache
    return cache


RepositorioDep = Annotated[Repositorio, Depends(obter_repositorio)]
GruposDep = Annotated[list[Grupo], Depends(obter_grupos)]
CatalogoDep = Annotated[Catalogo, Depends(obter_catalogo)]
CacheDep = Annotated[CacheLRU, Depends(obter_cache)]
