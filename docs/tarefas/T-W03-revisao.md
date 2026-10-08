# T-W03 — correções da revisão (PR #31) — branch `feat/frontend-graficos` — antes de seguir na T-W04
Caminhos em `apps/web/src/componentes/graficos/`.
1. `empilhado.ts:27-28,43,66`: total/domínio somam negativos (estornos) mas só v>0 é desenhado → barras
   passam do eixo e "Total" diverge. Usar `Math.max(0,v)` (ou tratar negativos explicitamente).
2. `empilhado.ts:23-24,44,58`: `throw` com >7 fontes derruba `atualizar`; cor depende da ordem dos dados.
   Fontes por opção em ordem fixa (cor estável); excedente agrupado em "Outras".
3. `base.ts:44-57`: `role="img"` + marcas focáveis é inconsistente. `<svg role="group" aria-label>` e
   `role="img"` + `aria-label` por marca (ou marcas sem foco e a tabela como alternativa).
4. `dispersao.ts:50,52`, `empilhado.ts:33`: `ticks(5,"~s")` sai en-US ("1.5k"). Usar
   `Intl.NumberFormat("pt-BR",{notation:"compact"})`.
5. `atualizar` com `replaceChildren` fecha o `<details>` e perde o foco: preservar `open` e o foco.
6. Testes: "atualizar não duplica svg/details/marcas" para todos os gráficos; casos negativo e >7 fontes;
   dispersão: zero dentro da calha (`xZero < x.range()[0]`).
