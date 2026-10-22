# Handoff frontend — T-W28

**Branch:** `feat/frontend-despesa-receita-por-voto` (test: → feat:)

## O que foi feito
- `dados/gastos-logica.ts`: `pontosDespesaReceitaPorVoto(g, base)` → `{pontos, semDados}`; x = `receita_por_voto`, y = `custo_voto_contratado|pago`; descarta null/≤0 (receita, despesa/voto, receita total) e conta.
- `dispersao.ts` generalizado por opção (sem mudar os gráficos atuais): `PontoCustoVoto.y`, `OpcoesDispersao.eixoY` e `diagonal` (y = x tracejada, rótulo "gastou o que arrecadou").
- `telas/gastos.ts`: h3 "Despesa por voto × receita por voto" depois de "Despesas e saldo"; segue a base contratado/pago e a busca; nota com "N candidatos sem dados" e aviso de contas parciais.
- Revisão T-W27: `destruir()` agora solta o tooltip fixo; `aria-label` do ponto selecionável (Redes) diz "Ao ativar, abre os dados e o link do perfil."
- Testes atualizados por consequência: 4 gráficos na tela (era 3); 3 linhas de referência no e2e (era 2).

## Decisões
- "Despesa ÷ receita" no tooltip = despesa da base ÷ `receita_total` (calculado no front, não usa `pct_receita_gasta`).
- Receita total ≤ 0 também fica de fora (receita/voto já seria 0).

## Pendências
Nenhuma. Alerta de declaração colorindo pontos fica para quando o backend expuser (T-A12 já na main, uso no front não pedido).

## Como verificar
`cd apps/web && pnpm tsc --noEmit && pnpm eslint src tests && pnpm vitest run && pnpm playwright test gastos-evolucao redes`
