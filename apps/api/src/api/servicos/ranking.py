"""Seleção declarativa "os N mais votados" (critério `ranking` de config/grupos.yaml)."""

from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.grupos import DefinicaoGrupo

# `ds_sit_tot_turno` do TSE para eleitos (QP ou média); "NÃO ELEITO" e "SUPLENTE" ficam de fora.
SITUACOES_ELEITO = frozenset({"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA"})


def selecionar_ranking(
    repo: Repositorio, grupo: DefinicaoGrupo, *, cargo: str, uf: str
) -> list[tuple[Candidatura, int]]:
    """Os `n` eleitos mais votados do cargo na UF, fora dos partidos excluídos.

    Ordem: votos nominais desc; empate → menor `sq_candidato` (determinístico). Devolve
    (candidatura, votos); menos de `n` eleitos elegíveis devolve menos (nunca completa).
    """
    regra = grupo.ranking
    assert regra is not None  # noqa: S101 - quem chama já separou os grupos por ranking
    elegiveis = [
        c
        for c in repo.candidaturas(grupo.ano, uf=uf, cargo=cargo)
        if c.ds_sit_tot_turno in SITUACOES_ELEITO and c.nr_partido not in regra.excluir_partido
    ]
    votos = repo.votos_totais(grupo.ano, [c.sq_candidato for c in elegiveis])
    pares = sorted(
        ((c, votos.get(c.sq_candidato, 0)) for c in elegiveis),
        key=lambda p: (-p[1], p[0].sq_candidato),
    )
    return pares[: regra.n]
