# Handoff backend — T-B05 (branch `feat/backend-densidade`)

## Feito
- Removido `_NATUREZA_DA_BIBLIOTECA` (CASE `ESTIMÁVEL`→`ESTIMADO`) de `repositorio/duckdb.py`; a view
  `receitas` lê `ds_natureza_receita` direto. `indicadores.financeiro` (T-A07) aceita o rótulo real.
  A fixture (`gerar_fixture.py`) já tinha `ESTIMÁVEL`, então o teste de integração cobre o caminho.
- `pytest` da API: 471 verdes, cobertura 95,8%; ruff/mypy limpos.

## Densidade (item 2) — pendente de dados
- `votos_local` e `locais_h3` **ainda não existem** em `.worktrees/dados/data/processed`; no branch
  `feat/dados-secao-h3` só há o commit de teste (implementação `etl/secao.py` não commitada).
- Alinhamento verificado no contrato em andamento (`contratos/tse.py`, working tree do dados):
  `locais_h3` tem `nr_local` e `h3` (res 8) — exatamente o que o repositório lê; extras (`lat`, `lon`,
  `h3_r7`, `h3_r6`, `aptos`, `nr_turno`, `cd_cargo`) são ignorados. `votos_local` idem.
  Sem mudança de código necessária, a menos que o dados altere nomes.
- Fixtures `votos_local.parquet` / `locais_h3.parquet` já existem em `apps/api/tests/fixtures` e
  os endpoints `/api/mapa/pontos` e `/api/mapa?nivel=h3` estão testados com elas.

## Falta (quando o dados entregar a saída real)
1. Rodar a API sobre `data/processed` com `votos_local`/`locais_h3` e o smoke (`scripts/smoke`).
2. Conferir limites de resultado por UF em `pontos`/`h3` com volume real (SP) e a res. H3 (ADR 0007).
3. Se o dados renomear colunas, ajustar `_COLUNAS` em `repositorio/duckdb.py:63-64`.

## Verificar
`uv run pytest apps/api -q` (web falha só por falta de `node_modules` neste worktree).
