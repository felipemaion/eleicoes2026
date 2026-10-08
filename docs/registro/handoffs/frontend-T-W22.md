# Handoff frontend — T-W22

Branch `fix/frontend-evolucao-ajustes` (a partir de `origin/main` 67f847d).

## Feito
1. **e2e da divisória** (`tests/e2e/mapa.spec.ts`): a causa provável era medir a caixa da divisória e as larguras logo após o mapa "pronto", quando canvas e barra de rolagem ainda se acomodam. Agora o teste espera o layout ficar idêntico por 5 `requestAnimationFrame` e refaz medição e arraste dentro de `toPass`. As asserções (+80 px no painel, −80 px no canvas) não mudaram. `--repeat-each=10` ficou 10/10 verde localmente. Não reproduzi a falha antes da correção, então a causa é hipótese.
2. **Evolução**: `filtros.ts` esconde o select "Grupo comparado" e a contagem de candidaturas quando `tela === "evolucao"`. Regra `[hidden]` no CSS, porque `display:flex` a anulava. Teste unitário novo.
3. **Textos do comparador**: `TEXTOS_COMPARADOR` agora sai de `src/textos.ts`, lendo `textos.json › comparador`. `telas/textos-comparador.ts` foi apagado. Textos novos, por vir do JSON: "indicado pelo MBL", "Voltar ao padrão", erro 422 e notas de grupo. Os e2e/unit que dependiam do texto antigo foram atualizados. A nota "Recorte: …" também vem do JSON (`recorte`).

## Verificar
`cd apps/web && pnpm vitest run && pnpm exec playwright test tests/e2e/mapa.spec.ts -g "arrastar muda" --repeat-each=10`

## Pendências
- Playwright usa `reuseExistingServer`: um `preview` antigo na :4173 serve um `dist/` defasado. Rode `pnpm build` antes de rodar os e2e localmente.
- Faltou `make lint test` completo num só comando (estourou o timeout). Rodei separado: eslint + tsc limpos, vitest 324/324, e2e do comparador, filtros e divisória verdes. Não rodei a suíte e2e inteira.
