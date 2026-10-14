#!/usr/bin/env bash
# Integra um PR só se TODOS os checks passarem (ou forem pulados de propósito).
#
# Existe porque um laço "espera e faz merge" já integrou um PR vermelho: o merge
# precisa depender do resultado, não só do fim da espera.
#
# Uso: integrar.sh <numero-do-pr>
set -euo pipefail
PR="${1:?numero do PR}"

# TDD (CLAUDE.md): PR feat/fix que mexe em código de produção precisa de um commit `test:` ANTES do
# primeiro `feat:`/`fix:` — é a prova de que o teste foi visto vermelho. Existe porque #90, #91 e #96
# entraram com teste e código num commit só e a revisão não pegou.
# Exceção consciente: TDD_EXCECAO="motivo" (fica no log e no comentário do PR).
checar_tdd() {
  local titulo commits codigo
  titulo="$(gh pr view "$PR" --json title --jq .title)"
  case "$titulo" in feat*|fix*) ;; *) return 0 ;; esac
  codigo="$(gh pr view "$PR" --json files --jq '[.files[].path | select(test("^(apps/[^/]+/src|packages/[^/]+/src)/"))] | length')"
  [ "$codigo" -gt 0 ] || return 0
  commits="$(gh pr view "$PR" --json commits --jq '.commits[].messageHeadline')"
  if printf '%s\n' "$commits" | awk '/^test/ {t=1} /^(feat|fix)/ {print (t ? "ok" : "falta"); exit}' | grep -qx ok; then
    return 0
  fi
  if [ -n "${TDD_EXCECAO:-}" ]; then
    echo "AVISO TDD: PR #$PR sem commit test: antes do feat/fix — exceção: $TDD_EXCECAO" >&2
    gh pr comment "$PR" --body "Integrado sem commit \`test:\` prévio (exceção TDD): $TDD_EXCECAO" >/dev/null
    return 0
  fi
  echo "NAO integrado: PR #$PR muda código e não tem commit test: (vermelho) antes do primeiro feat:/fix:." >&2
  echo "  Commits:" >&2; printf '    %s\n' "$commits" >&2
  echo "  Peça ao agente para separar o teste; exceção consciente: TDD_EXCECAO=\"motivo\" $0 $PR" >&2
  return 1
}
checar_tdd
[ -n "${INTEGRAR_SO_CHECAR:-}" ] && { echo "TDD ok: PR #$PR"; exit 0; }

# Logo após um push o GitHub ainda mostra os checks do commit anterior: dá tempo de o novo run nascer.
sleep "${INTEGRAR_ESPERA:-25}"

for _ in $(seq 1 90); do
  # Logo após o push os checks ainda não existem ("no checks reported"): conta como pendente.
  estados="$(gh pr checks "$PR" --json bucket --jq '[.[].bucket] | unique | join(",")' 2>/dev/null || true)"
  case "$estados" in
    ""|*pending*) sleep 10 ;;
    *) break ;;
  esac
done

gh pr checks "$PR" 2>/dev/null | awk -F'\t' '{print "  " $1 ": " $2}' || true
case "$estados" in
  *fail*|*cancel*|""|*pending*)
    echo "NAO integrado: PR #$PR com checks '$estados'" >&2
    exit 1 ;;
esac

gh pr merge "$PR" --squash  # branch remota é apagada pelo repo; a local pode estar numa worktree
echo "integrado: PR #$PR"
