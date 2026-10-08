# Handoff backend — T-B01 (scaffold da API)

**Branch:** `agente/backend` (worktree; renomear para `feat/backend-scaffold` ao abrir o PR).

## O que foi feito
- `apps/api/src/api/`: `main.py` (`criar_app`, lifespan, CORS restrito, gzip), `config.py`
  (pydantic-settings, prefixo `ELEICOES_`), `deps.py`, `repositorio/{base,duckdb,memoria}.py`,
  `servicos/meta.py`, `rotas/{saude,meta}.py`, `openapi.py`.
- `GET /api/health` → `{status, versao, dt_geracao}`; 503 `{detail:{codigo:"dados_indisponiveis"}}`.
- `GET /api/meta` → anos, UFs, cargos (dos dados) e grupos (`config/grupos.yaml`) + `dt_geracao`.
- Fixture provisória: `apps/api/tests/fixtures/{candidatos.parquet,manifesto.json}`, gerada por
  `apps/api/scripts/gerar_fixture.py`. `docs/api/openapi.json` gerado e conferido por teste.

## Decisões
- "Read-only": conexão `:memory:` + views sobre Parquet + `lock_configuration`; a API não tem
  nenhum caminho de escrita. (Não há arquivo .duckdb para abrir com `read_only=True`.)
- Contrato provisório de dados: `<dir_dados>/candidatos.parquet` (`ano, sg_uf, ds_cargo, …`) e
  `<dir_dados>/manifesto.json` com `dt_geracao`. **Alinhar com T-D02** quando sair.
- Dados que não abrem NÃO derrubam o processo: `/health` e `/meta` respondem 503 (gate de deploy).
- Testes usam `TestClient` (roda o lifespan) em vez de `AsyncClient`, evitando dependência extra.
- Entrypoint de produção: `uvicorn api.main:app_producao --factory --port 8000`.

## Pendências
- `make dev` ainda só imprime instrução; ajustar quando o orquestrador quiser (Makefile é dele).
- Dependência nova: `types-pyyaml` (dev) em `pyproject.toml` raiz/`uv.lock`.
- Cache HTTP (ETag), rate limit e paginação ficam para T-B02+.

## Como verificar
`make lint && make test` (59 testes, cobertura ~94%); `make openapi` não deve gerar diff.
