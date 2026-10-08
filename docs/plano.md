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
| T-D06 | dados | reproduzir no ETL a lista MBL 2022 já gerada (`data/reference/mbl_2022.csv`) com `pessoa_id` |
| T-B03 | backend | endpoints com dados reais, cache/ETag |
| T-W04 | frontend | telas: visão geral, mapa, gastos, evolução, ficha do candidato |
| T-A04 | analise | conferência dos números contra totais oficiais do TSE |

## Status em 2026-10-08 (fechamento)
- **F0–F3 concluídas.** Produção: https://eleicoes2026.maionesys.com — deploy automático na `main`
  (imagem arm64 no GHCR, bundle por rsync); dados por `make publicar-dados`.
- Integradas todas as tarefas planejadas: T-D01..T-D05, T-A01, T-A02 (+T-A03), T-A04..T-A07, T-B01..T-B06,
  T-W01..T-W09 e a lista MBL 2022 (18 candidaturas).
- Conferência com o TSE: diferença zero (`docs/metodologia/conferencia.md`); smoke de produção verde.
- Limitação conhecida: em 2022 o TSE não publica coordenada para 5,8% dos votos (BA/ES/SE ~26–30%) — a
  densidade desses estados é parcial e a API informa o peso fora do mapa.
- Backlog (F4): Moran/LISA no mapa, bivariado, cartograma, 2º turno, atualização automática das contas 2026,
  outros partidos (só configuração em `config/grupos.yaml`).
- Custo de desenvolvimento: `docs/registro/RELATORIO.md`.
