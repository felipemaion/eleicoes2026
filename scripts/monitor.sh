#!/usr/bin/env bash
# Painel-monitor: mostra os eventos do ledger conforme eles acontecem.
#
# E aqui que os subagentes in-process aparecem. Eles nao tem painel proprio —
# rodam dentro da sessao do agente que os chamou — mas passam por este registro,
# entao da para acompanhar a arvore inteira sem pagar um painel por folha.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARQUIVO="$RAIZ/docs/registro/ledger/$(date -u +%Y-%m).jsonl"

printf '\033[1mRegistro de tarefas\033[0m  %s\n\n' "${ARQUIVO#"$RAIZ/"}"
mkdir -p "$(dirname "$ARQUIVO")"
touch "$ARQUIVO"

tail -n 20 -F "$ARQUIVO" | "$RAIZ/scripts/formatar_eventos.py"
