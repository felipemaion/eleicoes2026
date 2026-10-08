# Handoff frontend — T-W03 (componentes D3)
Branch `feat/frontend-graficos` (parte de `feat/frontend-mapa`; **depende do PR #26/T-W02** — rebase após o merge).

## Feito
`apps/web/src/componentes/graficos/`: `kpi`, `barras`, `ranking` (reusa `barras`), `dispersao` (log), `empilhado`, `comparacao` (dumbbell), `multiplos` (barras com eixo comum), `base` (SVG acessível, tabela alternativa, `COR`).
Todos: `render(container, dados, opcoes)` → `{atualizar, destruir}`. `formato.ts` ganhou `localePtBR` (d3.formatLocale), `formatarMoeda` ("R$ 1.234,56") e `formatarNumero`.

## Decisões
- Dispersão: zeros (custo ou votos) vão para uma "calha" fora da faixa log, círculo vazado, classe `zero`, aria-label "custo zero"/"votos zero" e eixo marcado "0". Zeros sobrepostos coincidem no mesmo ponto (sem jitter).
- KPI é `<dl>` de texto: sem tabela alternativa (já é texto).
- Empilhado falha alto com >7 fontes (Okabe-Ito sem preto).
- Cores só de `PALETAS` (teste confere).

## Verificar
`cd apps/web && pnpm lint typecheck test build` (59 testes verdes). Testes: `tests/unit/graficos.test.ts`.

## Pendências
Ligar os gráficos nas telas (gastos, evolução, visão geral) quando houver dados da API; sem e2e novo.
