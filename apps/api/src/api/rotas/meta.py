"""GET /api/meta — anos, UFs, cargos e grupos."""

from fastapi import APIRouter

from api.deps import GruposDep, RepositorioDep
from api.servicos.meta import Meta, montar_meta

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=Meta, summary="Dimensões disponíveis para filtros")
def meta(repo: RepositorioDep, grupos: GruposDep) -> Meta:
    """Anos, UFs e cargos presentes nos dados + grupos configurados."""
    return montar_meta(repo, grupos)
