# Handoff frontend — T-W09 (e2e instável da densidade)
- **Causa:** em `apps/web/src/telas/mapa.ts` (l.118) o app desmarca e desabilita o checkbox ao receber 503 de `/mapa/pontos`. `locator.check()` confere o estado final "marcado"; se o 503 volta antes, falha com "did not change its state".
- **Correção (só teste):** `tests/e2e/mapa.spec.ts` usa `click()` e espera o resultado (aviso, `toBeDisabled`). Sem sleeps; o app não mudou.
- **Verificação:** `cd apps/web && npx playwright test mapa.spec.ts -g "pontos 503" --repeat-each=20` → 20/20 verdes.
- **Pendências:** nenhuma. Branch `fix/frontend-e2e-instavel`.
