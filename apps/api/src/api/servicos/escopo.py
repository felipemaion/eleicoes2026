"""Seleção do recorte (grupo ou candidato) e bases eleitorais por circunscrição."""

from api.erros import nao_encontrado, parametro_invalido
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.grupos import Catalogo, candidaturas_do_grupo


def selecionar_alvo(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    grupo_id: str | None,
    sq_candidato: int | None,
) -> list[Candidatura]:
    """Candidaturas do recorte: exatamente um de `grupo` ou `sq_candidato`, no cargo e ano."""
    if (grupo_id is None) == (sq_candidato is None):
        raise parametro_invalido(
            "alvo_ambiguo", "informe exatamente um entre 'grupo' e 'sq_candidato'"
        )
    if grupo_id is not None:
        grupo = catalogo.grupo(grupo_id)
        if grupo.ano != ano:
            raise parametro_invalido(
                "grupo_ano_incompativel", f"o grupo '{grupo_id}' é de {grupo.ano}, não de {ano}"
            )
        return candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo)
    assert sq_candidato is not None  # noqa: S101 - garantido pelo XOR acima
    candidatura = repo.candidatura(ano, sq_candidato)
    if candidatura is None:
        raise nao_encontrado("candidato_nao_encontrado", f"candidato {ano}/{sq_candidato}")
    if candidatura.ds_cargo != cargo or (uf is not None and candidatura.sg_uf not in (uf, "BR")):
        raise parametro_invalido(
            "candidato_fora_do_recorte", "o candidato não disputou esse cargo/UF"
        )
    return [candidatura]


def uf_da_base(sg_uf: str) -> str | None:
    """`BR` (presidente) usa a base nacional: sem filtro de UF."""
    return None if sg_uf == "BR" else sg_uf


class BasesPorEscopo:
    """Σ aptos e válidos por (ano, cargo, UF), consultados uma vez por escopo."""

    def __init__(self, repo: Repositorio) -> None:
        self._repo = repo
        self._cache: dict[tuple[int, str, str], tuple[int, int]] = {}

    def de(self, c: Candidatura) -> tuple[int, int]:
        """(aptos, validos) da circunscrição da candidatura."""
        chave = (c.ano, c.ds_cargo, c.sg_uf)
        if chave not in self._cache:
            linhas = self._repo.base_eleitoral(
                c.ano, c.ds_cargo, por_zona=False, uf=uf_da_base(c.sg_uf)
            )
            self._cache[chave] = (sum(b.aptos for b in linhas), sum(b.validos for b in linhas))
        return self._cache[chave]
