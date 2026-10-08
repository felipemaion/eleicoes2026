# Handoff frontend — T-W23 (tooltip cortado na borda direita)

**Branch:** `fix/frontend-tooltip-borda`

## Causa
Valores `nowrap` (T-W19) + rótulo longo ("Saldo (receita − despesa contratada)") excediam o `max-width: 22rem` da caixa; `posicionar` só ajustava a posição, o conteúdo transbordava a caixa e a tela.

## O que mudou
- `posicionar` (função pura): usa a largura **natural**; escolhe abaixo → acima → (caixa alta, sem espaço vertical) direita/esquerda. Só reduz largura se nem a tela inteira comporta, e sinaliza `comprimida`. Seta some nos lados laterais.
- `encaixar`: só fixa `maxWidth` quando `comprimida`.
- CSS: `.tooltip { min-width: min-content }`; **rótulos (`dt`) quebram linha**, valores (`dd`) seguem inteiros.
- Rótulo "Saldo (receita − despesa contratada)" → "Saldo" (detalhe já está no "?" `saldo_campanha` e na nota da seção). Vale para todos os tooltips de dados (mesmo componente: dispersões, ranking, mapa).
- Testes: 4 novos Vitest em `posicionamento.test.ts` (canto superior direito, borda inferior, caixa alta → lado, compressão); Playwright T-W23: hover no ponto mais à direita e mais acima de Receita×votos e Despesa×votos, em 1280 e 700 px — caixa dentro da viewport e nenhum elemento com `scrollWidth > clientWidth`.

## Verificar
`cd apps/web && npx vitest run && npx tsc --noEmit && npx eslint src tests && npx playwright test` (mate o preview na :4173 antes: `reuseExistingServer` serve build velho).

Capturas: `docs/registro/handoffs/img/T-W23-balao-1280.png`, `T-W23-balao-700.png`.

## Pendências
Nenhuma. Tooltips laterais não têm seta (decisão consciente, caso raro).
