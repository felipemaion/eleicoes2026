# 0003 — Comparação temporal por município e H3, não por zona

- **Status:** aceito · 2026-10-07
- **Contexto:** zona eleitoral não tem polígono oficial e houve rezoneamento entre 2022 e 2026.
- **Decisão:** zona é exibida dentro de cada ano (Voronoi dos locais de votação recortado pelo
  município). Comparações 2022×2026 usam município (código IBGE) e hexágonos H3 agregados dos
  locais de votação (resolução definida pelo analista em T-A01).
- **Consequências:** comparação honesta; zona com mesmo número em anos diferentes nunca é pareada.
