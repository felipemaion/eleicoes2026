"""Normalização de texto para busca: sem acento, minúsculas, mesma regra em Python e em SQL."""

import unicodedata

# DuckDB: strip_accents(lower(x)). Python: NFD sem marcas combinantes + lower.
SQL_NORMALIZA = "strip_accents(lower({coluna}))"


def normalizar(texto: str) -> str:
    """`'César'` → `'cesar'`; aparas nas pontas, espaços internos colapsados."""
    decomposto = unicodedata.normalize("NFD", texto.lower())
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.split())


def escapar_like(texto: str) -> str:
    """Escapa `%`, `_` e `\\` para o termo valer como texto num LIKE ... ESCAPE '\\'."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
