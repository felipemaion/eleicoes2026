# Handoff frontend — T-W29

**Branch:** `feat/frontend-serie-variacao-rotulo` (test: → feat:), a partir de `origin/main` (independe da T-W28).

## O que foi feito
- `formato.ts`: `formatarVariacao({abs, pct, dias})` → `+1.234 (+2,1%)`; `−` tipográfico, zero sem sinal, `null` no 1º ponto, `em N dias` quando o intervalo > 1 dia (nunca interpola).
- `serie-tempo.ts`: `PontoTempo.variacao?` (opcional; sem ele nada muda). Rótulo `text.variacao-trecho` (classe `alta|queda|neutra`) no meio de cada trecho, acima da linha, com halo; omitido se o trecho for mais estreito que o texto (6,6 px/caractere + 10) — assim os rótulos não se sobrepõem nem saem da área. Variação também no `aria-label`, no tooltip e numa coluna "Variação" da tabela alternativa.
- `redes.ts`: passa `delta_abs/delta_pct/dias` da API (sem recalcular).
- Cores: Okabe-Ito azul (alta) / vermelhão (queda), como nas outras dispersões; o sinal no texto repete a direção.

## Decisões
- % com 1 casa e sem espaço (`+2,1%`), como no brief; o resumo acima do gráfico mantém o formato antigo (`+0,65 %`) — não toquei nele.
- Rótulos de trechos curtos ficam só no tooltip/tabela (critério 3).

## Pendências
Nenhuma.

## Como verificar
`cd apps/web && pnpm tsc --noEmit && pnpm eslint src tests && pnpm vitest run && pnpm playwright test redes`
