# Handoff frontend — T-W16 (receitas na interface)

Branch `feat/frontend-receitas`. `pnpm lint`, `tsc`, Vitest (340) e Playwright (67; 89 de produção/API real ficam skipped) verdes.

## O que mudou
- **Tela "Gastos" virou "Financiamento"** (rótulo e h1; a rota continua `#/gastos` para não quebrar links). Seções:
  1. **Receitas** — KPIs (receita total líquida do grupo, receita por voto, % público, % autofinanciamento, % pessoas físicas, saldo), cada um com "?" e "fonte"; nota da **faixa honesta** quando há repasse de doador desconhecido; barra empilhada por fonte (hover); **dispersão receita × votos** (hover com foto, saldo, % PF; clique abre o TSE; linha tracejada = mediana de receita por voto).
  2. **Despesas e saldo** — custo por voto contratado/pago, dívida e a dispersão custo × votos de antes. O saldo por candidato (receita − despesa contratada) está no balão.
  3. **2022 × 2026 corrigido pelo IPCA** — tabela (2022 corrigido, 2022 publicado, 2026, variação em % ou p.p.) vinda de `/comparativo.receitas`, com mês-base e aviso de contas parciais. Carrega à parte: se falhar, só ela some.
- A busca por nome realça o candidato nas **duas** dispersões.
- Tipos regenerados do OpenAPI (`receitas` agora `null`-ável). Sem receita declarada, a tela diz isso em vez de desenhar zero (`null` ≠ 0).
- Ficha do candidato: ganhou receita por voto e saldo; receita total some se `null`.
- `dispersao.render` ganhou `grandeza` (vocabulário do eixo/tabela/aviso de zero); padrão inalterado.
- Lógica pura nova: `src/dados/receitas-logica.ts` (testes em `tests/unit/receitas-logica.test.ts`). Textos dos "?" vêm de `textos.json` (nada redigido no front, só rótulos de coluna e duas notas curtas).
- Fixtures `gastos`, `comparativo` e `ficha` atualizadas ao contrato novo.

## Decisões / pendências
- Saldo por candidato **não** tem gráfico próprio (barras não suportam valor negativo): fica em KPI do grupo + balão. Se quiserem ranking divergente de saldo, é uma tarefa nova.
- A composição por fonte é do **grupo**; `/gastos` não traz fontes por candidato.
- A comparação usa os lados `de`/`para` da URL, como a Evolução (padrão: comparação do grupo).

## Como verificar
`cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm exec playwright test` → abrir `#/gastos?uf=SE`. Atenção: o Playwright reaproveita o `vite preview` da porta 4173; rode `pnpm build` antes se houver um antigo no ar.
