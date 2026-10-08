"""Manifesto de downloads: registro reprodutível de cada arquivo bruto."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entrada:
    """Metadados de um arquivo baixado."""

    url: str
    caminho: str  # relativo a data/raw
    sha256: str
    bytes: int
    baixado_em: str  # ISO 8601 UTC
    etag: str | None = None
    last_modified: str | None = None
    dt_geracao: str | None = None  # preenchido ao ler o CSV (T-D02)


class Manifesto:
    """Mapa url → :class:`Entrada`, persistido em JSON ordenado e escrito atomicamente."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.entradas: dict[str, Entrada] = {}
        if caminho.exists():
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
            self.entradas = {u: Entrada(**e) for u, e in bruto.items()}

    def obter(self, url: str) -> Entrada | None:
        """Entrada registrada para ``url``, se houver."""
        return self.entradas.get(url)

    def por_caminho(self, caminho: str) -> Entrada | None:
        """Entrada cujo arquivo (relativo a data/raw) é ``caminho``."""
        return next((e for e in self.entradas.values() if e.caminho == caminho), None)

    def registrar(self, entrada: Entrada) -> None:
        """Insere/substitui a entrada e persiste."""
        self.entradas[entrada.url] = entrada
        self.salvar()

    def salvar(self) -> None:
        """Grava via arquivo temporário + rename: nunca deixa JSON truncado."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = {u: asdict(self.entradas[u]) for u in sorted(self.entradas)}
        texto = json.dumps(dados, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        tmp = self.caminho.with_suffix(self.caminho.suffix + ".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, self.caminho)
