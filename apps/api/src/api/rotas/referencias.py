"""Rota de referências: HTTP fino; a regra vive em `servicos/referencias.py`."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from api.deps import CacheDep, CatalogoDep, RepositorioDep
from api.dominio import UF, Cargo
from api.servicos.referencias import Referencias, montar_referencias

router = APIRouter(tags=["referencias"])
_ERROS: dict[int | str, dict[str, Any]] = {
    422: {
        "description": "Cargo sem grupo de referência, UF ausente (deputados) ou `sq` que não é "
        "candidato nosso no recorte."
    }
}


@router.get(
    "/referencias",
    response_model=Referencias,
    summary="Nossos candidatos × candidatos de referência",
    responses=_ERROS,
)
def referencias(
    repo: RepositorioDep,
    catalogo: CatalogoDep,
    cache: CacheDep,
    cargo: Cargo,
    uf: Annotated[
        UF | None,
        Query(description="Obrigatória para deputados; ignorada para presidente (nacional)."),
    ] = None,
    sq: Annotated[
        int | None, Query(description="Candidato nosso a destacar (`destacado = true`).")
    ] = None,
) -> Referencias:
    """Dois lados nomeados: `nossos` (Missão no cargo/UF) e `referencia`.

    Presidente: os presidenciáveis do grupo de referência. Deputados: os 5 eleitos mais votados
    de outros partidos na UF. Cada candidato traz indicadores em taxa; `indices` (nossos) é o
    valor ÷ mediana da referência. Descritivo: candidaturas de estruturas muito diferentes.
    Finanças ausentes vêm nulas com motivo, nunca zero.
    """
    uf_v = uf.value if uf else None
    return cache.obter(
        repo.versao_dados(),
        ("referencias", cargo.value, uf_v, sq),
        lambda: montar_referencias(repo, catalogo, cargo=cargo, uf=uf_v, sq=sq),
    )
