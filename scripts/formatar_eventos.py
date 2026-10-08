#!/usr/bin/env python3
"""Formata os eventos do ledger para leitura no painel-monitor.

Le JSONL da entrada padrao e escreve uma linha colorida por evento. Linha
invalida e ignorada: o monitor le um arquivo sendo escrito, entao encontrar uma
linha pela metade e normal, nao e erro.
"""

from __future__ import annotations

import json
import sys

RESET = "\033[0m"
NEGRITO = "\033[1m"
CORES = {"inicio": "\033[32m", "fim": "\033[34m", "revisao": "\033[33m"}


def formatar(evento: dict[str, object]) -> str:
    """Monta a linha de uma acao: hora, acao, papel, tarefa e descricao."""
    acao = str(evento.get("acao", ""))
    hora = str(evento.get("timestamp", ""))[11:19]
    papel = str(evento.get("papel", ""))
    tarefa = str(evento.get("task", ""))
    descricao = str(evento.get("descricao", ""))
    cor = CORES.get(acao, "")
    return f"{hora}  {cor}{acao:<8}{RESET} {NEGRITO}{papel:<12}{RESET} {tarefa:<10} {descricao}"


def main() -> int:
    for linha in sys.stdin:
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(evento, dict):
            print(formatar(evento), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
