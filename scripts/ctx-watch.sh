#!/usr/bin/env bash
# Mostra o uso de contexto de cada painel de agente, lido da status line (ctx:NN%).
#
# O orquestrador usa isto para manter cada agente abaixo de 70%: ao fim de uma
# tarefa, ou acima de LIMITE_AVISO, pede handoff, envia /clear e recondiciona.
#
# Saida: "<papel> <pct> <estado>" por linha; estado = ok | handoff | CRITICO.
# Codigo de saida 2 se algum painel estiver em CRITICO (>= LIMITE_CRITICO).
set -euo pipefail

LIMITE_AVISO="${LIMITE_AVISO:-60}"
LIMITE_CRITICO="${LIMITE_CRITICO:-70}"
critico=0

while read -r painel papel; do
  [ -n "$papel" ] || continue
  pct="$(tmux capture-pane -p -t "$painel" | grep -oE 'ctx:[0-9]+%' | tail -1 | tr -dc '0-9' || true)"
  pct="${pct:-?}"
  estado=ok
  if [ "$pct" != "?" ]; then
    if [ "$pct" -ge "$LIMITE_CRITICO" ]; then estado=CRITICO; critico=1
    elif [ "$pct" -ge "$LIMITE_AVISO" ]; then estado=handoff; fi
  fi
  printf '%-10s %4s%% %s\n' "$papel" "$pct" "$estado"
done < <(tmux list-panes -a -F '#{pane_id} #{@papel}')

[ "$critico" = 0 ] || exit 2
