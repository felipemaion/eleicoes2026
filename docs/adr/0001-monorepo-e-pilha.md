# 0001 — Monorepo com uv + pnpm; FastAPI, D3 e MapLibre

- **Status:** aceito · 2026-10-07
- **Contexto:** pedido explícito por FastAPI e D3.js com sistema de mapa; quatro agentes em paralelo.
- **Decisão:** monorepo (`etl/`, `packages/`, `apps/api`, `apps/web`) com workspace `uv` (Python 3.12)
  e `pnpm` (TypeScript). Mapa base MapLibre GL (open source, sem API key); D3 v7 para escalas,
  legendas e gráficos. Sem framework de UI.
- **Consequências:** contratos e docs num só lugar; territórios por pasta evitam conflito entre
  agentes; MapLibre dá zoom até local de votação, o que D3 puro não daria bem.
