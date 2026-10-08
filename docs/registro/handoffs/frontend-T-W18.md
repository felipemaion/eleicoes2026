# Handoff frontend — T-W18 (divisória mapa × painel, tabela legível)

**Branch:** `feat/frontend-divisoria-mapa` · captura: `frontend-T-W18.png`

## O que foi feito
- `componentes/ui/divisoria.ts`: `limitarLargura`/`larguraPorTecla` (puras, Vitest) + `criarDivisoria`
  (pointer events + `setPointerCapture`, `role=separator`, `aria-value*`, ←/→ (Shift = passo grande), Home/End,
  duplo clique restaura, `localStorage` com try/catch). Escondida ≤1100px (layout empilhado).
- `telas/mapa.ts`: grade `mapa | divisória | painel` com `--painel-largura`; mínimos: mapa 20rem, painel 15rem.
  `ResizeObserver` no layout reaplica o limite se a janela encolher, sem esquecer a largura pedida.
- Tabela do painel (`painel-municipio.ts`): cabeçalhos curtos com `title` ("Cand.", "Votos", "Aptos",
  "Penetr. (‰)", "% válidos"), células numéricas `nowrap` + `tabular-nums` à direita, ‰ só no cabeçalho,
  rolagem horizontal dentro de `.tabela-rolavel` (classe já existente). Regras duplicadas de `.painel-municipio table` removidas.

## Decisões
- Não chamei `map.resize()` à mão: o MapLibre 6 observa o contêiner; o e2e confirma que o canvas acompanha o arraste.
  `aoRedimensionar` (rAF) existe na divisória como gancho, sem uso hoje.
- Seta ← aumenta o painel (a linha anda para a esquerda), coerente com o painel à direita.

## Pendências
- `mapa.spec.ts › mapa carrega…` (hover no centro) oscilou 2× em rodadas completas e passa isolado (4/4);
  parece corrida com a sobreposição "Carregando…", anterior a esta tarefa.
- O Playwright reutiliza o preview da :4173: rode `pnpm build` antes, senão testa o bundle antigo.

## Como verificar
`cd apps/web && pnpm vitest run && pnpm build && pnpm exec playwright test tests/e2e/mapa.spec.ts`
