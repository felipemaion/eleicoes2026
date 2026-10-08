"""GET /api/health — gate de deploy."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.deps import RepositorioDep
from api.repositorio.base import DadosIndisponiveis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["saude"])


class Saude(BaseModel):
    """Estado da API e dos dados."""

    status: str
    versao: str
    dt_geracao: str


@router.get("/health", response_model=Saude, summary="Saúde da API e DT_GERACAO dos dados")
def health(repo: RepositorioDep, request: Request) -> Saude:
    """200 quando os dados abrem; 503 caso contrário."""
    try:
        repo.ping()
    except DadosIndisponiveis as erro:
        logger.error("ping dos dados falhou: %s", erro)
        raise HTTPException(status_code=503, detail={"codigo": "dados_indisponiveis"}) from erro
    return Saude(status="ok", versao=request.app.state.versao_app, dt_geracao=repo.dt_geracao())
