#!/usr/bin/env bash
# Atualiza a borda do painel tmux de um agente e registra o evento no ledger.
#
# Borda e registro saem daqui juntos, de proposito: se fossem dois comandos,
# um dia divergiriam e o painel mentiria sobre o que o agente esta fazendo.
#
# Uso: agent-title.sh <papel> <acao> [tarefa] [descricao]
#   agent-title.sh backend inicio T-014 "motor de ToolInstance"
#   agent-title.sh backend fim T-014
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPEL="${1:?informe o papel: dados, analise, backend, frontend}"
ACAO="${2:?informe a acao: inicio, fim ou revisao}"
TAREFA="${3:-}"
DESCRICAO="${4:-}"

# O modelo vem do frontmatter da definicao do agente: uma fonte de verdade so.
definicao="$RAIZ/.claude/agents/$PAPEL.md"
[[ -f "$definicao" ]] || { echo "papel desconhecido: $PAPEL" >&2; exit 1; }
alias_modelo="$(awk -F': *' '/^model:/ {print $2; exit}' "$definicao")"

case "$ACAO" in
  inicio) rotulo="${TAREFA:-tarefa} ${DESCRICAO}" ;;
  fim)    rotulo="ocioso (ultima: ${TAREFA:-—})" ;;
  *)      rotulo="${ACAO} ${TAREFA}" ;;
esac

# Localiza o painel pela opcao @papel, nao pelo titulo: o Claude Code mantem o
# titulo (nome do agente e atividade) e sobrescreveria qualquer coisa nossa.
# Basta o servidor tmux existir. Condicionar a $TMUX so funcionaria para quem
# chama de dentro de um painel — o orquestrador chama de fora.
if command -v tmux >/dev/null && tmux list-panes -a >/dev/null 2>&1; then
  alvo="$(tmux list-panes -a -F '#{pane_id} #{@papel}' \
          | awk -v p="$PAPEL" '$2 == p {print $1; exit}')"
  [ -n "$alvo" ] && tmux set -p -t "$alvo" @tarefa "$rotulo"
fi

# O ledger guarda o id completo do modelo; o titulo mostra o apelido curto.
# Sem array associativo: o bash do macOS ainda e o 3.2.
case "$alias_modelo" in
  opus)   modelo=claude-opus-5-5 ;;
  sonnet) modelo=claude-sonnet-5-5 ;;
  haiku)  modelo=claude-haiku-4-5 ;;
  *)      modelo="$alias_modelo" ;;
esac

"$RAIZ/scripts/ledger.py" evento \
  --task "${TAREFA:-sem-tarefa}" \
  --papel "$PAPEL" \
  --modelo "$modelo" \
  --acao "$ACAO" \
  --descricao "$DESCRICAO" \
  --branch "$(git -C "$RAIZ" branch --show-current 2>/dev/null || echo '')"
