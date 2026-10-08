"""Consultas em cache compartilhadas pelas rotas e pelo aquecimento.

Uma só definição da chave de cache e do cálculo: o aquecimento só serve se gravar exatamente
a chave que a rota vai ler (por isso rota e aquecimento chamam estas funções).
"""

from collections.abc import Sequence

from api.cache_servico import CacheLRU
from api.dominio import Cargo
from api.repositorio.base import Repositorio
from api.servicos.candidatos import ListaCandidatos, listar_candidatos
from api.servicos.comparativo import Comparativo, montar_comparativo
from api.servicos.gastos import Gastos, montar_gastos
from api.servicos.grupos import Catalogo


def candidatos_em_cache(
    repo: Repositorio,
    catalogo: Catalogo,
    cache: CacheLRU,
    *,
    grupo: str,
    uf: str | None,
    cargo: str | None,
    limite: int,
    offset: int,
) -> ListaCandidatos:
    """`/candidatos` com cache LRU (chave inclui `dt_geracao`)."""
    return cache.obter(
        repo.dt_geracao(),
        ("candidatos", grupo, uf, cargo, limite, offset),
        lambda: listar_candidatos(
            repo, catalogo, grupo_id=grupo, uf=uf, cargo=cargo, limite=limite, offset=offset
        ),
    )


def gastos_em_cache(
    repo: Repositorio,
    catalogo: Catalogo,
    cache: CacheLRU,
    *,
    grupo: str,
    uf: str | None,
    cargo: str | None,
) -> Gastos:
    """`/gastos` com cache LRU."""
    return cache.obter(
        repo.dt_geracao(),
        ("gastos", grupo, uf, cargo),
        lambda: montar_gastos(repo, catalogo, grupo_id=grupo, uf=uf, cargo=cargo),
    )


def comparativo_em_cache(
    repo: Repositorio,
    catalogo: Catalogo,
    cache: CacheLRU,
    *,
    comparacao: str | None,
    cargo: Cargo,
    uf: str | None,
    mesmos_candidatos: bool,
    pessoas: Sequence[str] = (),
    sq_2022: Sequence[int] = (),
    sq_2026: Sequence[int] = (),
    grupo_2022: str | None = None,
    grupo_2026: str | None = None,
) -> Comparativo:
    """`/comparativo` com cache LRU."""
    return cache.obter(
        repo.dt_geracao(),
        (
            "comparativo",
            comparacao,
            cargo,
            uf,
            mesmos_candidatos,
            tuple(sorted(pessoas)),
            tuple(sorted(sq_2022)),
            tuple(sorted(sq_2026)),
            grupo_2022,
            grupo_2026,
        ),
        lambda: montar_comparativo(
            repo,
            catalogo,
            comparacao_id=comparacao,
            cargo=cargo,
            uf=uf,
            mesmos_candidatos=mesmos_candidatos,
            pessoas=pessoas,
            sq_2022=sq_2022,
            sq_2026=sq_2026,
            grupo_2022=grupo_2022,
            grupo_2026=grupo_2026,
        ),
    )
