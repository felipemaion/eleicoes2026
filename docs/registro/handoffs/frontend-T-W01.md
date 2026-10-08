# Handoff frontend — T-W01 (scaffold web)

## O que foi feito
- `apps/web/`: pnpm + Vite + TS estrito + ESLint (strictTypeChecked) + Vitest (jsdom) + Playwright; deps D3, MapLibre GL, pmtiles.
- `src/store.ts` (estado tipado, `criarStore`), `src/rotas.ts` (hash ↔ store; só grava na URL o que difere do padrão), `src/paletas.ts` (paletas, temas, `contraste`, CSS das cores), `src/tokens.css` (tokens não cromáticos), 5 telas placeholder em `src/telas/`, filtros UF/cargo/grupo/ano, `src/dados/cliente.ts` (stub `meta()`), rodapé com fonte e `dt_geracao`.
- Testes: 9 unitários (store, hash, paletas/contraste AA) e 3 e2e (navegação mouse/teclado, filtro→URL, 360 px sem rolagem horizontal).

## Decisões
- Cores têm fonte única em `paletas.ts`; o CSS é injetado no `<head>` (evita duplicar em tokens.css). Tema escuro via `prefers-color-scheme`, com override `data-tema`.
- Paletas: Blues 7 (sequencial), PuOr 7 (divergente, neutro no índice 3), Okabe-Ito 8 (categórica).
- Pins: `typescript@6` (typescript-eslint ainda não suporta TS 7) e `jsdom@26` (jsdom 30 quebra no Node 20).
- Rodapé busca `GET /api/meta` (`{dt_geracao, fonte}`); sem API, mostra "indisponível". **Pendência para o backend:** endpoint `/meta` não existe no contrato ainda.
- Sem `openapi-typescript` ainda: `docs/api/openapi.json` não existe; adicionar script `gen:api` quando houver.

## Como verificar
`cd apps/web && pnpm install && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm exec playwright install chromium && pnpm test:e2e`

## Pendências
- Campo de seleção de candidato e contêineres reais: T-W02/T-W03.
- CI ainda não roda Playwright (só `make lint test`).
