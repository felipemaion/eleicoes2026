"""Dependências injetadas (FastAPI Depends); nada de globais."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from api.repositorio.base import Repositorio
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


RepositorioDep = Annotated[Repositorio, Depends(obter_repositorio)]
GruposDep = Annotated[list[Grupo], Depends(obter_grupos)]
