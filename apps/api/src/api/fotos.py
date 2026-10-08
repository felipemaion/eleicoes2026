"""Fotos oficiais dos candidatos: manifesto da T-D07 (`<dados>/fotos/manifesto.json`).

A API só informa a URL; o arquivo `/fotos/<ano>/<sq>.webp` é servido pelo Caddy.
"""

import json
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, Field

from api.links import Link, link_tse_candidato

PREFIXO = "/fotos"


def ler_manifesto(dir_dados: Path) -> frozenset[tuple[int, int]]:
    """Pares (ano, sq_candidato) com foto; vazio se o manifesto não existe (fotos opcionais)."""
    arquivo = dir_dados / "fotos" / "manifesto.json"
    if not arquivo.is_file():
        return frozenset()
    chaves = json.loads(arquivo.read_text())["fotos"]
    return frozenset((int(a), int(sq)) for a, sq in (k.split("/") for k in chaves))


def foto_url(disponiveis: frozenset[tuple[int, int]], ano: int, sq_candidato: int) -> str | None:
    """URL relativa da foto, ou `None` quando o TSE não publicou (front mostra avatar neutro)."""
    if (ano, sq_candidato) not in disponiveis:
        return None
    return f"{PREFIXO}/{ano}/{sq_candidato}.webp"


class ComFotoELink(BaseModel):
    """Campos de identificação visual e oficial que toda lista de candidatos carrega."""

    foto_url: str | None = Field(
        description="Foto oficial (WebP 160×200), relativa à raiz do site; null se o TSE não "
        "publicou a foto dessa candidatura."
    )
    link_tse_candidato: Link = Field(
        description="Página do candidato no DivulgaCandContas (perfil, bens, contas); "
        "`verificado = true`: padrão aberto no navegador para 2022 e 2026."
    )


class FotoELink(TypedDict):
    """Valores dos campos de `ComFotoELink`."""

    foto_url: str | None
    link_tse_candidato: Link


def foto_e_link(
    disponiveis: frozenset[tuple[int, int]], *, ano: int, sq_candidato: int, uf: str
) -> FotoELink:
    """Valores dos campos de `ComFotoELink` de uma candidatura (para `**` no construtor)."""
    return {
        "foto_url": foto_url(disponiveis, ano, sq_candidato),
        "link_tse_candidato": link_tse_candidato(ano=ano, sq_candidato=sq_candidato, uf=uf),
    }
