#!/usr/bin/env bash
# Resolve um papel de agente para o identificador do painel tmux.
#
# Enderecar por indice quebrou na pratica: um agente dividiu a propria janela
# para lancar revisores, os indices deslocaram, e comandos passariam a cair no
# painel errado. Identificador de painel nao muda.
#
# Falha alto quando nao encontra. A alternativa — devolver vazio — faz o
# `tmux send-keys -t ""` acertar o painel ativo. Isso ja mandou instrucao de
# agente para o terminal do usuario duas vezes neste projeto.
set -euo pipefail
PAPEL="${1:?informe o papel: dados, analise, backend ou frontend}"
alvo="$(tmux list-panes -a -F '#{pane_id} #{@papel}' 2>/dev/null | awk -v p="$PAPEL" '$2 == p {print $1; exit}')"
[ -n "$alvo" ] || { echo "papel sem painel: $PAPEL" >&2; exit 1; }
echo "$alvo"
