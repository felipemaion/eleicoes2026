#!/usr/bin/env bash
# Snapshot diário do Instagram (T-D08, ADR 0008). Roda pelo launchd (ver com.eleicoes2026.redes.plist).
#
# A Graph API limita ~200 chamadas/hora. A 1ª rodada completa leva horas; as seguintes, ~1 chamada por
# perfil. O ETL sai com código 3 ao bater no limite (progresso e cache do dia ficam em disco), e este
# laço espera e retoma até concluir. Qualquer outro código de saída encerra: token/permissão exigem
# ação humana. Aviso de token a ≤15 dias do vencimento sai no stderr do ETL (ver o log).
#
# Variáveis: REDES_TENTATIVAS (padrão 10) · REDES_ESPERA_S (padrão 3600)
set -u
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ" || exit 1
# o launchd não herda o PATH do shell interativo (uv fica em ~/.local/bin ou no Homebrew)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

tentativas="${REDES_TENTATIVAS:-10}"
espera="${REDES_ESPERA_S:-3600}"

uv run etl redes-tse --baixar || exit $?
for i in $(seq 1 "$tentativas"); do
  uv run etl redes-coletar
  codigo=$?
  [ "$codigo" -ne 3 ] && exit "$codigo"
  echo "$(date '+%F %T') limite de chamadas (tentativa $i/$tentativas); retomando em ${espera}s" >&2
  sleep "$espera"
done
echo "limite de chamadas persistiu após $tentativas tentativas" >&2
exit 3
