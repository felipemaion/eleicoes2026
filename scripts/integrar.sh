#!/usr/bin/env bash
# Integra um PR só se TODOS os checks passarem (ou forem pulados de propósito).
#
# Existe porque um laço "espera e faz merge" já integrou um PR vermelho: o merge
# precisa depender do resultado, não só do fim da espera.
#
# Uso: integrar.sh <numero-do-pr>
set -euo pipefail
PR="${1:?numero do PR}"

for _ in $(seq 1 90); do
  estados="$(gh pr checks "$PR" --json bucket --jq '[.[].bucket] | unique | join(",")' 2>/dev/null || true)"
  case "$estados" in
    ""|*pending*) sleep 10 ;;
    *) break ;;
  esac
done

gh pr checks "$PR" | awk -F'\t' '{print "  " $1 ": " $2}'
case "$estados" in
  *fail*|*cancel*|""|*pending*)
    echo "NAO integrado: PR #$PR com checks '$estados'" >&2
    exit 1 ;;
esac

gh pr merge "$PR" --squash --delete-branch
echo "integrado: PR #$PR"
