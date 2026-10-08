# Changelog
Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · Conventional Commits.

## [Não lançado]

## [0.1.0] — 2026-10-08
### Adicionado
- ETL de fontes oficiais (TSE 2022/2026, IBGE, BCB) com contratos Parquet, totais de controle e `pessoa_id`.
- Biblioteca `indicadores` (desempenho, espaciais, financeiros, evolução) validada por vetores da spec.
- API FastAPI (DuckDB read-only) com cache, quebras comuns 2022+2026, limites de recursos.
- Dashboard (Vite/TS, D3, MapLibre, PMTiles): 5 telas, acessível, textos públicos.
- Conferência contra os totais do TSE (diferença zero) e deploy em eleicoes2026.maionesys.com.
### Adicionado
- F0: estrutura do monorepo, CLAUDE.md, documentação (arquitetura, fontes, metodologia, agentes,
  deploy), ADRs 0001–0006, definições dos 4 agentes, scripts de orquestração, CI e briefs de F1.
