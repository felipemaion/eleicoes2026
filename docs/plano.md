# Plano de fases

Plano aprovado em 2026-10-07. Tarefas detalhadas em `docs/tarefas/T-*.md`; estado vivo nas Issues.

| Fase | Objetivo | Paralelismo |
|---|---|---|
| **F0** Bootstrap | repo, CLAUDE.md, docs, agentes, scripts, CI, briefs | orquestrador |
| **F1** Fundações | dados brutos → Parquet; spec e lib de indicadores; scaffolds API e web contra fixtures | 4 painéis em paralelo |
| **F2** Integração | lista MBL 2022; endpoints reais; telas; conferência com TSE | 4 painéis |
| **F3** Publicação | Docker ARM64, deploy com Oracle, segurança, E2E, README | orquestrador + backend/frontend |
| **F4** Backlog | Moran/LISA, bivariado, cartograma, outros partidos, 2º turno, contas automáticas | — |

## F1 — tarefas
| ID | Papel | Tarefa | Depende de |
|---|---|---|---|
| T-D01 | dados | downloader com manifesto e cache | — |
| T-D02 | dados | contratos + parsers (candidatos, votação munzona, detalhe, legenda, locais) | T-D01 |
| T-D03 | dados | prestação de contas (receitas/despesas) | T-D01 |
| T-D04 | dados | municípios: crosswalk TSE↔IBGE, malhas, PMTiles | T-D01 |
| T-D05 | dados | votação por seção → local de votação → H3 | T-D02, T-D04 |
| T-A01 | analise | spec completa dos indicadores com vetores de teste | — |
| T-A02 | analise | lib indicadores: desempenho + financeiros | T-A01, contratos (T-D02) |
| T-A03 | analise | lib indicadores: espaciais (LQ, HHI, Ames) + evolução | T-A02 |
| T-B01 | backend | scaffold FastAPI, Repository, health/meta sobre fixtures | começa com fixture provisória; alinha ao contrato de T-D02 |
| T-B02 | backend | contrato OpenAPI dos endpoints | T-A01 |
| T-W01 | frontend | scaffold Vite/TS, tokens de design, layout e roteamento | — |
| T-W02 | frontend | componente de mapa MapLibre (coroplético + densidade) sobre fixture | T-W01 |
| T-W03 | frontend | componentes D3 (barras, ranking, scatter, small multiples) | T-W01 |

Primeira leva em paralelo: **T-D01, T-A01, T-B01, T-W01**.

## F2 — tarefas
| ID | Papel | Tarefa |
|---|---|---|
| T-D06 | dados | casamento da lista MBL 2022 (**aguarda arquivo do Felipe**) |
| T-B03 | backend | endpoints com dados reais, cache/ETag |
| T-W04 | frontend | telas: visão geral, mapa, gastos, evolução, ficha do candidato |
| T-A04 | analise | conferência dos números contra totais oficiais do TSE |
