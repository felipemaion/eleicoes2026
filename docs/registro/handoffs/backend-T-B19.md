# Handoff backend — T-B19

**Branch:** `feat/backend-redes-dir-status` (a partir da `origin/main`; T-B18 já estava na main como #89).

## O que foi feito
- `ELEICOES_REDES_DIR` (`Settings.redes_dir`): onde ficam `redes_perfis.parquet`, `redes_posts.parquet`,
  `manifesto.json` e `status.json`. Padrão = `<dir_dados>/redes` (local e produção atual não mudam).
  `redes_candidatos` (TSE, reconstruível) continua em `dir_dados`.
- Recarga sem restart: `RepositorioDuckDB` compara o mtime de `manifesto.json` + os dois Parquet da série,
  no máximo 1×/`ELEICOES_REDES_RECARGA_S` (60 s), chamado em `versao_dados()`/`redes_meta()`. Mudou → recria as
  views (`CREATE OR REPLACE VIEW`) e recalcula a coleta; `versao_dados()` muda, logo ETag e cache LRU mudam.
- Recarga que falha (arquivo quebrado/colunas) loga ERROR, mantém o último estado bom e tenta de novo na
  próxima checagem (a assinatura só avança no sucesso).
- `/api/health` ganhou `redes: {coletado_em, resultado, motivo, dias_desde_ultima_coleta_ok} | null`.
  Health não tem cache HTTP, então os dias são ao vivo. `status.json` ausente/ilegível → `resultado`/`motivo`
  nulos; sem status e sem dados de redes → `redes: null`.
- `infra/compose.yaml`: volume `${REDES_DIR:-../data/redes}:/redes:ro` + `ELEICOES_REDES_DIR=/redes`.
- OpenAPI regenerado; `smoke.py` confere o bloco `health.redes` quando presente.

## Decisões
- `dias_desde_ultima_coleta_ok` e `coletado_em` valem para a última coleta **boa**: `status.coletado_em` se
  `resultado == "ok"`, senão a coleta que está nos dados (`max(coletado_em)` dos snapshots). Uma tentativa
  `erro`/`limite` não zera o relógio.
- Status em `/api/health`, não em `/api/redes`: o corpo de `/redes*` é cacheado por ETag e os dias mudam
  sem o dado mudar.
- O Parquet é substituído pelo ETL por rename atômico; a assinatura inclui os Parquet além do manifesto
  para pegar promoção que não toque o manifesto.

## Pendências / para o Oracle
- Montar `/home/…/data/redes` em `/redes:ro` e definir `ELEICOES_REDES_DIR=/redes` no compose do servidor.
- Formato do `status.json` assumido da T-D09: `{inicio, fim, resultado: ok|limite|erro, motivo,
  perfis_coletados, coletado_em}` (ISO-8601 UTC); a API só lê `resultado`, `motivo`, `coletado_em`.

## Como verificar
`make lint test` (871 passed). Específicos: `uv run pytest apps/api/tests/test_b19_redes_dir.py`.
