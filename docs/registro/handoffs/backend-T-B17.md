# Handoff backend — T-B17 (ETag inclui a versão do build)

## O que foi feito
- `Settings.versao_app` (env `ELEICOES_VERSAO_APP`), sem default. `criar_app` levanta `RuntimeError` se faltar
  (produção via `app_producao` falha no startup).
- ETag = sha256(`dt_geracao | versao_app | hash12(OpenAPI) | path | query`). O hash do OpenAPI é calculado
  uma vez ao montar a app (reforço do sha). `/api/health` devolve `versao` = `versao_app` (antes "0.1.0").
- `apps/api/Dockerfile`: `ARG VERSAO_APP` → `ENV ELEICOES_VERSAO_APP` (sem default).
- `Makefile` `dev`: `ELEICOES_VERSAO_APP=dev` por padrão. `conftest.py`: `"teste"`. `openapi.py`: `"openapi"`.
- OpenAPI inalterado (`info.version` segue `VERSAO` = 0.1.0, contrato estável).

## deploy.yml (feito, commit ci: separado, autorizado pelo orquestrador)
`.github/workflows/deploy.yml`, passo `docker/build-push-action@v6`, precisa de:
```yaml
build-args: |
  VERSAO_APP=${{ github.sha }}
```
**Mergear junto**: sem isso a imagem nova não sobe (falha alto por design) e o gate do health reverte.
Se o compose do Oracle define env próprio, a variável da imagem basta (não precisa mudar).

## Verificar
`uv run pytest apps/api/tests/test_b17_etag_versao.py`; `make lint` (py) e `uv run pytest --cov`: 664 passed.
(`make test`/`lint` do web falham aqui só por `node_modules` ausente no worktree.)
Em produção: `curl .../api/health` mostra o sha em `versao`.
