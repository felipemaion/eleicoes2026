# 0007 — Penetração como âncora, H3 res 8 canônica e AMC para a série temporal

- **Status:** proposto (analise, T-A01) · 2026-10-07
- **Contexto:** ADR 0003 fixou município e H3 para comparar 2022 × 2026, deixando a resolução e
  o denominador para o analista. Escolhas aqui afetam o contrato dos Parquet (`locais_votacao.h3`,
  tabela de AMC) e a API, por isso viram ADR.
- **Decisão:**
  1. **Métrica-âncora** de toda comparação temporal: penetração = votos / aptos × 1000 (‰).
     % de válidos fica como secundária.
  2. **H3 canônica res 8** (gravada por local de votação, coordenadas do próprio ano); res 7/6/5
     derivadas por soma de contagens. **Comparação temporal em res 7 (urbano) e 6 (estadual)**.
  3. **AMC** (área mínima comparável) para a série municipal: desmembramentos 2022→2026 agregados
     ao(s) município(s) de origem; tabela produzida pelo `dados` a partir do IBGE.
  4. Local de votação sem coordenada válida fica fora do H3 (nunca no centróide), com
     `pct_votos_sem_coordenada` publicado por município.
  5. Indicadores nunca somam cargos; Senado fica fora da evolução (1 vaga em 2022, 2 em 2026).
- **Consequências:** `locais_votacao` ganha `h3_r8` e flag de coordenada válida; nova tabela
  `amc` (`cd_mun_ibge → amc`); API expõe `resolucao ∈ {5,6,7,8}` e `turno`. Detalhes e vetores em
  `docs/metodologia/indicadores.md` (seções 1.1, 1.2, 1.8, 5.1).
