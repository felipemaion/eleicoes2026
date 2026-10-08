#!/usr/bin/env bash
# Envia uma tarefa a um agente: atualiza titulo/ledger e manda o brief ao painel.
#
# O brief vive em docs/tarefas/T-xxx.md; no painel vai so um ponteiro curto,
# sempre identificando o remetente (orquestrador) — o agente le o arquivo.
#
# Uso: despachar.sh <papel> <T-xxx> "<descricao curta>" [--limpar]
#   --limpar: envia /clear antes (recondicionar contexto entre tarefas)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPEL="${1:?papel}"; TAREFA="${2:?T-xxx}"; DESCRICAO="${3:?descricao}"; LIMPAR="${4:-}"
BRIEF="docs/tarefas/$TAREFA.md"
[ -f "$RAIZ/$BRIEF" ] || { echo "brief inexistente: $BRIEF" >&2; exit 1; }

alvo="$("$RAIZ/scripts/pane-do-papel.sh" "$PAPEL")"

if [ "$LIMPAR" = "--limpar" ]; then
  tmux send-keys -t "$alvo" "/clear" C-m
  sleep 2
fi

"$RAIZ/scripts/agent-title.sh" "$PAPEL" inicio "$TAREFA" "$DESCRICAO" >/dev/null

msg="[Do orquestrador Eleicoes2026 (tmux Eleicoes2026:orq)] Nova tarefa $TAREFA — $DESCRICAO. Leia $BRIEF (caminho relativo a raiz do repo; você está na sua worktree, onde o arquivo também existe após git pull/rebase da main). Siga CLAUDE.md e sua definição de agente. Ao terminar, escreva o handoff em docs/registro/handoffs/$PAPEL-$TAREFA.md e responda só 'pronto $TAREFA'."
tmux send-keys -t "$alvo" -l "$msg"
sleep 0.5
tmux send-keys -t "$alvo" Enter
echo "despachado: $PAPEL <- $TAREFA"
