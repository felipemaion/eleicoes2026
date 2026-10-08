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


def nivel_relevancia(
    nm_urna: str,
    nm_civil: str | None,
    sg_partido: str,
    nr_candidato: int | None,
    nr_partido: int,
    termo: str,
) -> int:
    """Nível de relevância (0 = melhor) de uma candidatura para o termo já normalizado.

    Texto: 0 nome de urna exato · 1 começo do nome (urna ou civil) · 2 começo de palavra
    (urna, civil ou sigla) · 3 trecho. Número: 0 número exato · 1 prefixo do número · 2 partido.
    Espelha `_nivel` do repositório DuckDB; os dois precisam andar juntos.
    """
    if termo.isdigit():
        numero = str(nr_candidato or "")
        if numero == termo:
            return 0
        return 1 if numero.startswith(termo) else 2
    urna, civil, sigla = normalizar(nm_urna), normalizar(nm_civil or ""), normalizar(sg_partido)
    if urna == termo:
        return 0
    if urna.startswith(termo) or civil.startswith(termo):
        return 1
    if any(c.startswith(termo) or f" {termo}" in c for c in (urna, civil, sigla)):
        return 2
    return 3
