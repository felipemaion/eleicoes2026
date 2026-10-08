"""Perfis de Instagram de uma candidatura e o bloco `redes` da ficha.

Fica separado de `redes.py` porque a ficha (`candidatos.py`) usa estes modelos e `redes.py`
usa `Partido` de `candidatos.py`: juntos formariam um ciclo de importação.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from api.fontes import FonteRede, fontes_redes
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.redes_base import (
    ANO_REDES,
    STATUS_NAO_COLETADO,
    BaseRedes,
    em_utc,
    link_instagram,
    montar_base,
    username_da_chave,
)


class PerfilRede(BaseModel):
    """Um perfil declarado ao TSE, com a última coleta (campos nulos se não há números)."""

    username: str
    link: str = Field(description="Endereço público do perfil no Instagram.")
    url_tse: str | None = Field(description="Texto declarado ao TSE; null se só a coleta o tem.")
    principal: bool = Field(description="Declarado primeiro ao TSE (menor `NR_ORDEM`).")
    analisado: bool = Field(
        description="Conta usada nos indicadores: a de mais seguidores entre as com números."
    )
    status: str = Field(
        description="`ok`, `nao_encontrado` (pessoal ou inexistente), `nao_comercial` ou "
        "`nao_coletado` (declarado, ainda sem coleta). Só `ok` traz números."
    )
    seguidores: int | None = Field(description="null = indisponível (≠ zero).")
    seguindo: int | None
    n_midias: int | None = Field(description="Posts da vida inteira da conta (`media_count`).")
    coletado_em: datetime | None = Field(description="Última coleta (UTC); null se nunca coletado.")


class BlocoRedes(BaseModel):
    """Bloco `redes` da ficha: perfis e última coleta."""

    perfis: list[PerfilRede] = Field(description="Vazio = não declarou Instagram ao TSE.")
    coletado_em: datetime = Field(description="Coleta mais recente do Instagram (UTC).")
    fontes: list[FonteRede]


def _perfil(
    base: BaseRedes,
    sq: int,
    username: str,
    url_tse: str | None,
    principal: bool,
    analisada: str | None,
) -> PerfilRede:
    s = base.ultimo.get((sq, username))
    return PerfilRede(
        username=username,
        link=link_instagram(username),
        url_tse=url_tse,
        principal=principal,
        analisado=username == analisada,
        status=s.status if s else STATUS_NAO_COLETADO,
        seguidores=s.seguidores if s else None,
        seguindo=s.seguindo if s else None,
        n_midias=s.n_midias if s else None,
        coletado_em=em_utc(s.coletado_em) if s else None,
    )


def perfis_do_candidato(base: BaseRedes, sq: int) -> list[PerfilRede]:
    """Declarados (em ordem) + coletados não declarados; `analisado` vem dos indicadores."""
    linha = base.linha(sq)
    analisada = (
        username_da_chave(str(linha["username"]))
        if linha["tem_dados"] and linha["username"]
        else None
    )
    declarados = base.declaradas.get(sq, [])
    perfis = [_perfil(base, sq, d.username, d.url_tse, d.principal, analisada) for d in declarados]
    vistos = {d.username for d in declarados}
    perfis += [
        _perfil(base, sq, username, None, False, analisada)
        for (s, username) in base.ultimo
        if s == sq and username not in vistos
    ]
    return perfis


def bloco_ficha(repo: Repositorio, candidatura: Candidatura) -> BlocoRedes | None:
    """Bloco `redes` da ficha; `None` se não há redes publicadas ou o ano não tem coleta."""
    meta = repo.redes_meta()
    if meta is None or candidatura.ano != ANO_REDES:
        return None
    base = montar_base(repo, meta, [candidatura])
    return BlocoRedes(
        perfis=perfis_do_candidato(base, candidatura.sq_candidato),
        coletado_em=em_utc(meta.coletado_em),
        fontes=fontes_redes(
            ano=base.ano, dt_geracao_tse=meta.dt_geracao_tse, coletado_em=meta.coletado_em
        ),
    )
