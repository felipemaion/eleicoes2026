"""Caso de uso /meta: o que existe nos dados e nos grupos configurados."""

from pathlib import Path

import yaml
from pydantic import BaseModel

from api.repositorio.base import Repositorio


class Grupo(BaseModel):
    """Grupo comparável definido em config/grupos.yaml."""

    id: str
    rotulo: str
    ano: int


class Meta(BaseModel):
    """Dimensões disponíveis para filtros."""

    anos: list[int]
    ufs: list[str]
    cargos: list[str]
    grupos: list[Grupo]
    dt_geracao: str


def carregar_grupos(arquivo: Path) -> list[Grupo]:
    """Lê os grupos do YAML; arquivo ausente falha alto."""
    bruto = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    return [Grupo(id=gid, rotulo=g["rotulo"], ano=g["ano"]) for gid, g in bruto["grupos"].items()]


def montar_meta(repo: Repositorio, grupos: list[Grupo]) -> Meta:
    """Combina o que os dados contêm com os grupos configurados."""
    return Meta(
        anos=sorted(repo.anos()),
        ufs=sorted(repo.ufs()),
        cargos=sorted(repo.cargos()),
        grupos=grupos,
        dt_geracao=repo.dt_geracao(),
    )
