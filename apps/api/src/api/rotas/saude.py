"""GET /api/health — gate de deploy."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.config import VERSAO
from api.deps import RepositorioDep

router = APIRouter(tags=["saude"])


class Saude(BaseModel):
    """Estado da API e dos dados."""

    status: str
    versao: str
    dt_geracao: str


@router.get("/health", response_model=Saude, summary="Saúde da API e DT_GERACAO dos dados")
def health(repo: RepositorioDep) -> Saude:
    """200 quando os dados abrem; 503 caso contrário."""
    return Saude(status="ok", versao=VERSAO, dt_geracao=repo.dt_geracao())
