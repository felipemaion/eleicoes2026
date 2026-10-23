# Handoff frontend — T-W30

Branch `fix/frontend-dispersao-aria-diagonal` (base origin/main).

## Feito
1. `dispersao.ts`: `aria-label` só diz "e o link do perfil" quando há `linkExterno` https.
2. Teste da diagonal agora prova y = x (ponto com custo == y cai sobre a reta; custo ≠ y, fora).
3. Comentário "Reta do ajuste log-log…" de volta acima de `desenharReta`.
4. `formatarVariacao`: `dias === null` → " em intervalo não informado" (antes sumia como 1 dia); pct que arredonda a 0,0 sem sinal.
5. (prioridade) `serie-tempo.ts`: acabou o rótulo fixo. Todo trecho tem linha de captura transparente (16 px) + realce; no hover o balão mostra "dd/mm → dd/mm" + Variação (com "em N dias"). Removida a regra de omitir trecho estreito. Teclado/leitor: variação segue no ponto e na tabela.

## Decisões / pendências
- Texto para `dias` nulo escolhido por mim ("em intervalo não informado"); ajustar se preferir.
- Hover do trecho é só mouse (trecho não é focável, para não duplicar a informação do ponto).
- Item 5: implementação e testes foram escritos juntos (sem commit vermelho separado); itens 1–4 tiveram `test:` vermelho antes.

## Verificar
`cd apps/web && npx vitest run tests/unit && npx tsc --noEmit && npx eslint src tests && npx playwright test tests/e2e/redes.spec.ts`
