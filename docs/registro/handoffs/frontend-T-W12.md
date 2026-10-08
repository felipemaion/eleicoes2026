# Handoff frontend — T-W12 (gastos com hover, evolução com escolha, ficha rastreável)

Branch `feat/frontend-gastos-evolucao` (sobre `origin/main` com T-W11). Lint, tsc, 277 testes unitários e 55 e2e verdes.

## O que foi feito
- **Contrato**: `pnpm gen:api` (T-B07/B08 trouxeram `fontes`, `links`, gastos completos, `/evolucao/pessoas`). Fixtures atualizadas e nova `pessoas.json`; `tipado.ts` estreita `tipo` de link e abrangência.
- **Gastos**: tooltip rico por círculo (hover/foco/Esc; partido, UF, cargo, votos, despesa contratada/paga, custo por voto, resultado), linha tracejada da mediana de custo por voto, busca que realça/atenua (`destacar()` sem redesenhar), hover nas barras de receita (valor e % da receita), "fonte" nos KPIs.
- **Evolução**: seletor (busca com debounce, "só indicados", atalhos "Grupo inteiro"/"Só indicados", rascunho + "Comparar selecionados"), seleção no hash (`pessoas=a,b`), `/api/comparativo?pessoas=` (parâmetro repetido), KPIs e 3 mapas do conjunto, tabela 2022×2026 ordenável (aria-sort). 422 `sem_par_comparavel` vira mensagem explicativa.
- **Ficha**: seção "Gastos de campanha" (contratado, pago, dívida, repasses, receita, custo por voto com e sem repasses + explicação), botões dos links oficiais (nova aba, aviso se `verificado=false`), botão "fonte" (dataset, DT_GERACAO, regra, arquivo oficial, metodologia) em KPIs/gastos/receitas.
- Código novo: `dados/gastos-logica.ts`, `dados/evolucao-logica.ts`, `telas/evolucao-selecao.ts`, `telas/evolucao-tabela.ts`, `fonteUi` em `telas/textos-ui.ts`.

## Decisões
- Marcar candidatos não navega: só "Comparar selecionados" grava o hash (cada mudança de hash redesenha a tela e recria 3 mapas WebGL).
- Cargo/UF do seletor vêm da barra de filtros (mesmos do comparativo).
- Penetração por pessoa vem das fichas 2022 e 2026 (2 chamadas/pessoa), limitada a 12 escolhidos; ausente aparece como "—" com aviso.

## Pendências / pedidos ao backend
- `/gastos` não traz partido, resultado nem % público por candidato: partido/resultado vêm de `/candidatos` (mesmo recorte, limite 500); **% público por candidato não aparece no tooltip**. Pedido: incluir `pct_publico` em `GastoCandidato`.
- `/evolucao/pessoas` não filtra por ids: pessoa escolhida (hash) fora das 200 primeiras do recorte não aparece na tabela (há aviso). Pedido: parâmetro `pessoas=` nesse endpoint.
- Zoom/brush na dispersão (opcional no brief) não feito.

## Como verificar
`cd apps/web && pnpm exec eslint . && pnpm exec tsc --noEmit && pnpm exec vitest run && pnpm exec playwright test` (e2e novo: `tests/e2e/gastos-evolucao.spec.ts`).

## Capturas
`docs/registro/handoffs/img/T-W12-gastos-hover.png`, `-gastos-busca.png`, `-evolucao-selecao.png`, `-evolucao-tabela.png`, `-ficha-fonte.png`.
