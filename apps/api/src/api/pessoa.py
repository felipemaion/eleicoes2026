"""Identificador público de pessoa: liga as candidaturas de uma pessoa entre anos sem expor o hash.

O `pessoa_id` do ETL (hash salgado de CPF/título) nunca sai pela API. O que sai é um derivado
truncado e não reversível, estável entre cargas, só para o front ligar 2022↔2026. A mesma fórmula
roda em SQL (`SQL_ID_PUBLICO`) e em Python (`id_publico`); um teste garante que concordam.
"""

import hashlib

PREFIXO = "pub:"  # separa este derivado de qualquer outro uso do hash
TAMANHO = 12
SQL_ID_PUBLICO = f"substr(sha256('{PREFIXO}' || pessoa_id), 1, {TAMANHO})"


def id_publico(pessoa_id: str) -> str:
    """Hash curto e não reversível do `pessoa_id` (12 hex)."""
    return hashlib.sha256((PREFIXO + pessoa_id).encode()).hexdigest()[:TAMANHO]
