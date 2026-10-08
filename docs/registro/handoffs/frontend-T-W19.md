# Handoff frontend — T-W19 (balões de ajuda não quebravam linha)

**Branch:** `fix/frontend-tooltip-quebra`

## Causa
O balão de ajuda fica dentro de `.kpi-fim` (`white-space: nowrap`) e herdava o nowrap; além disso a T-W17
pôs nowrap em `.tooltip-lista dt/dd`, regra compartilhada.

## Correção (`estilo.css`, `tooltip.ts`)
- `.tooltip { white-space: normal }` — cortam a herança de qualquer ancestral nowrap (+ `overflow-wrap: anywhere` já existente).
- nowrap só em `.tooltip-lista--dados` (a lista de rótulo curto + número, única usuária de `.tooltip-lista`).
- Usos conferidos: ajuda (KPIs, mapa, gastos, evolução, ficha) = `.ajuda-painel` dentro de `.tooltip`; dados = `tooltip-lista--dados`.

## Testes
- e2e novo (`gastos-evolucao.spec.ts`): balão de KPI da Evolução com `white-space: normal`, `scrollWidth <= clientWidth`, dentro da viewport. Visto falhar antes da correção (`nowrap`).
- Unit da T-W17 ajustado para a classe nova; e2e completo verde.

## Nota
Os `docs/registro/handoffs/img/T-W12-*.png` são regravados por `apps/web/tests/e2e/gastos-evolucao.spec.ts`
(testes de evolução, `page.screenshot` em `CAPTURAS`) a cada rodada do e2e; restaurei da origin/main antes do commit.
