#!/usr/bin/env bash
# Sobe o ambiente de agentes do Eleicoes2026 em tmux.
#
# A sessao "Eleicoes2026" ja existe (janela 0 = orquestrador). Este script
# acrescenta:
#   agentes — um painel por papel (dados, analise, backend, frontend), cada um
#             uma sessao claude de vida longa dentro da sua worktree
#   infra   — monitor do ledger e shells da API e do web
#
# Idempotente: se a janela "agentes" ja existe, nao duplica paineis.
# ELEICOES_DRY_RUN=1 monta o layout sem iniciar os agentes (sem pagar o boot).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSAO="${ELEICOES_TMUX:-Eleicoes2026}"
PAPEIS="${ELEICOES_PAPEIS:-dados analise backend frontend}"
SECO="${ELEICOES_DRY_RUN:-}"

command -v tmux >/dev/null || { echo "tmux nao encontrado" >&2; exit 1; }
[ -n "$SECO" ] || command -v claude >/dev/null || { echo "claude nao encontrado no PATH" >&2; exit 1; }

tmux has-session -t "$SESSAO" 2>/dev/null || tmux new-session -d -s "$SESSAO" -n orq -c "$RAIZ"

if tmux list-windows -t "$SESSAO" -F '#{window_name}' | grep -qx agentes; then
  echo "janela 'agentes' ja existe em '$SESSAO' — nada a fazer"
  exit 0
fi

tmux set -t "$SESSAO" -g mouse on
tmux setw -t "$SESSAO" -g pane-border-status top
tmux setw -t "$SESSAO" -g pane-border-format \
  ' #{?@papel,#{@papel},#{pane_title}}#{?@modelo, · #{@modelo},}#{?@tarefa, · #{@tarefa},} '

modelo_de() { awk -F': *' '/^model:/ {print $2; exit}' "$RAIZ/.claude/agents/$1.md"; }

# Uma worktree por agente: sem isso, um agente trocando de branch puxa o tapete
# dos outros e o sintoma aparece no agente errado.
worktree_de() {
  caminho="$RAIZ/.worktrees/$1"
  if [ ! -d "$caminho" ]; then
    git -C "$RAIZ" worktree add --quiet -B "agente/$1" "$caminho" main >/dev/null 2>&1 \
      || git -C "$RAIZ" worktree add --quiet "$caminho" "agente/$1" >/dev/null 2>&1
  fi
  echo "$caminho"
}

# O diretorio e definido na criacao do painel (-c). Um `cd` por send-keys corre
# contra a inicializacao do shell e se perde.
primeiro=1
for papel in $PAPEIS; do
  arvore=$(worktree_de "$papel")
  modelo=$(modelo_de "$papel")
  if [ "$primeiro" = 1 ]; then
    painel=$(tmux new-window -P -F '#{pane_id}' -t "$SESSAO" -n agentes -c "$arvore")
    primeiro=0
  else
    painel=$(tmux split-window -P -F '#{pane_id}' -t "$SESSAO:agentes" -c "$arvore")
    tmux select-layout -t "$SESSAO:agentes" tiled >/dev/null
  fi
  # Papel e modelo vivem em opcoes do painel: o Claude Code sobrescreve o titulo.
  tmux set -p -t "$painel" @papel "$papel"
  tmux set -p -t "$painel" @modelo "$modelo"
  tmux select-pane -t "$painel" -T "$papel"
  # Publicar e integrar é do orquestrador: push/PR/merge negados só aos agentes. O settings.json
  # do projeto vale também para a sessão do orquestrador, que precisa publicar.
  comando="claude --agent $papel --model $modelo --permission-mode auto --disallowedTools 'Bash(git push:*)' 'Bash(gh pr merge:*)' 'Bash(gh pr create:*)'"
  [ -n "$SECO" ] && comando="echo '[verificacao] $comando'"
  tmux send-keys -t "$painel" "clear && $RAIZ/scripts/agent-title.sh $papel fim >/dev/null && $comando" C-m
done

tmux new-window -t "$SESSAO" -n infra -c "$RAIZ"
tmux select-pane -t "$SESSAO:infra" -T "registro"
tmux send-keys -t "$SESSAO:infra" "$RAIZ/scripts/monitor.sh" C-m
tmux split-window -t "$SESSAO:infra" -c "$RAIZ"
tmux select-pane -t "$SESSAO:infra" -T "ctx-watch"
tmux send-keys -t "$SESSAO:infra" "watch -n 30 $RAIZ/scripts/ctx-watch.sh" C-m
tmux select-layout -t "$SESSAO:infra" tiled >/dev/null

echo "janelas 'agentes' ($PAPEIS) e 'infra' criadas em '$SESSAO'"
