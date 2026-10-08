# 0002 — DuckDB + Parquet read-only; ETL local

- **Status:** aceito · 2026-10-07 (recomendação do agente Oracle)
- **Contexto:** dados somente leitura, recarga diária durante a apuração das contas; servidor ARM64
  com 2 OCPU compartilhadas por 4 serviços; sem Postgres; backup cobre só SQLite.
- **Decisão:** Parquet particionado por ano/UF consultado por DuckDB embutido na API
  (`threads=2`). ETL roda local; só Parquet sobe via rsync para `datasets/`.
- **Consequências:** nenhum daemon novo nem backup novo (dado reprodutível); geometria resolvida no
  ETL (sem extensão espacial). Reavaliar PostGIS só com consulta espacial dinâmica real.
