# Handoff frontend — T-W02 (mapa MapLibre + escalas D3)
Branch `feat/frontend-mapa` (sobre `feat/frontend-scaffold`, que inclui as correções da revisão do PR #25).

## O que foi feito
- `src/componentes/escalas/escalas.ts`: `escalaQuantil`, `escalaLimiar` (mesmas quebras 2022/2026), `escalaDivergente` (centro 0, swing), `escalaLog` (centro 1, LQ), `expressaoCor` (`case`+`step` do MapLibre), `validarCoropletico` (recusa `tipo:'absoluto'` com sugestão de símbolos proporcionais; exige unidade e denominador). `legenda.ts`: legenda SVG a partir da mesma escala.
- `src/componentes/mapa/`: `criarMapa(container, opcoes)` → `{pronto, definirValores, definirNivel, definirPontos, estatisticas, destruir}`. Fonte abstrata `geojson` ou `pmtiles` (`pmtiles://`), valores por `feature-state` (trocar indicador não recarrega geometria: `estatisticas().fontesCarregadas` fica em 1). Densidade: heatmap + circle (raio ∝ √votos). Tooltip (mouse e teclado: setas/Home/End/Esc) com votos, taxa e eleitorado; tabela alternativa em `<details>`.
- `src/telas/mapa.ts`: tela usa a fixture de Sergipe (75 municípios, `tests/fixtures/`; valores sintéticos, só demonstração), com 3 indicadores (penetração/swing/LQ). MapLibre carregado por `import()` dinâmico.
- `src/formato.ts`: formatação pt-BR.

## Decisões
- `definirValores(valores, escala, meta, detalhes?)` (o brief citava `(mapa, escala)`): `meta` carrega tipo/unidade/denominador para validação e legenda.
- Worker do MapLibre via `setWorkerUrl(...?url)`; sem isso o build do Vite não renderiza tiles (erro "Worker failed to load").
- Quantis com empates (muitos zeros) removem quebras repetidas e reduzem o nº de classes (não esconde: `escala.quebras` reflete).
- `escalaDivergente`/`escalaLog` usam `scaleLinear`/`scaleLog` só para posicionar as quebras simétricas e `scaleThreshold` para classificar; `scaleDiverging` (contínuo) não foi usado porque o mapa é por classes.
- Níveis `zona`/`h3`: `definirNivel` já troca camadas, mas só funciona se `opcoes.fontes` trouxer a fonte (falha alto se não).

## Pendências
- PMTiles real (T-D04): ainda não testado contra arquivo `.pmtiles`; só o caminho GeoJSON tem e2e.
- Chunk do MapLibre >500 kB (esperado, carregado sob demanda).
- Fixture com valores sintéticos: não usar como dado real.

## Como verificar
`cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e` (e2e roda `pnpm build`). Manual: `pnpm dev` → `#/mapa`.
