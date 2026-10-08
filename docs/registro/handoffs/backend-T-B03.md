# Handoff backend — T-B03 (dados reais, quebras comuns, Docker arm64)
Branch `feat/backend-dados-reais` (sobre `fix/analise-indicadores-revisao` = PR #34; **integrar #34 antes**).
Nota: `docs/tarefas/T-B03.md` no checkout principal mudou para um stub durante a tarefa; segui o brief detalhado lido no início.

## Feito
- **Quebras comuns**: `/mapa?comparacao=<id>&grupo=<um dos lados>` e `/comparativo` (campo novo `escala_sugerida`) usam `indicadores.espacial.quebras_comuns` (k=5, sem `n_baixo`). `escala_sugerida.anos` lista os anos. Dados insuficientes → `quebras: null` + `aviso` (nunca lista inventada). xfail removido.
- **Dados reais** (`ELEICOES_DIR_DADOS=<data/processed>`); o smoke real achou e corrigi:
  - `ds_cargo` vem "Deputado Federal" → views fazem `upper()`.
  - receitas/despesas/IPCA agora lidos de `receitas_candidatos`, `despesas_*_candidatos`, `ipca/ipca.parquet` (fixtures regeneradas no layout real).
  - linhas "sem movimento" (origem/fonte nulas e valor 0) filtradas; natureza `ESTIMÁVEL`→`ESTIMADO` mapeada na view.
  - `tp_prestacao_contas`: manifesto > proporção FINAL ≥95 % no dado > PARCIAL (2026 ⇒ PARCIAL).
  - `municipios` cacheado em memória (cold do comparativo BR: 1,7 s → 1,05 s).
- **Smoke**: `uv run python apps/api/scripts/smoke.py [--base URL]` — 14 verificações, Kim 2022 = 295.460 ✔, 2026 = 520.071 ✔; sai 1 se p95 quente ≥500 ms ou frio ≥2 s.
- **Docker**: `apps/api/Dockerfile` (multi-stage, uv, arm64, user 10001, `--factory`, HEALTHCHECK) + `Dockerfile.dockerignore`; `infra/compose.yaml` espelho (rede `proxy` externa, sem ports, cpus 1.0, mem 2g, datasets :ro, rootfs read-only). Build arm64 ok (38 s, 133 MB); container `healthy`, smoke 14/14 contra ele. Env em runtime: `ELEICOES_DIR_DADOS=/datasets`, `ELEICOES_ARQUIVO_GRUPOS`, `ELEICOES_RAIZ_REPOSITORIO=/app`, `ELEICOES_CORS_ORIGINS` (JSON). Build no GitHub Actions: `docker buildx build --platform linux/arm64 -f apps/api/Dockerfile .` (contexto = raiz).

## Latência (p50 / p95 quente; frio) — Mac M-series nativo, dados reais
| endpoint | frio | p50 | p95 |
|---|---|---|---|
| mapa SP município | 145 ms | 2 | 2 |
| mapa SP zona | 117 ms | 2 | 3 |
| mapa Brasil | 465–509 ms | 8 | 11 |
| mapa SP quebras comuns | 280–315 ms | 2 | 3–5 |
| comparativo SP | 300 ms | 3 | 5 |
| comparativo Brasil | 1,1 s | 14 | 15 |
| candidatos SP | 430 ms | 1 | 2 |
| gastos SP | 440 ms | 1 | 2 |
No container Docker Desktop (1 CPU, bind virtiofs) o frio de comparativo BR foi 2,7–3,0 s (>2 s); medir no Oracle após o deploy. Quente: tudo <20 ms (cache LRU).

## Mudanças de contrato OpenAPI (avisar frontend)
`/mapa` +`comparacao`; `EscalaSugerida.anos`; `Comparativo.escala_sugerida`; `Comparativo.n_de/n_para` agora `int|null` (null = TSE não publicou `ds_situacao_candidatura`, nulo em todo 2026 hoje); `CandidatoResumo.situacao` anulável. `docs/api/openapi.json` regenerado.

## Compose do Oracle
`ELEICOES_DUCKDB_THREADS` aceito (alias de `threads`); caminhos de grupos/CSV absolutos por env na imagem (independem do cwd); testado com rootfs read-only e `/datasets` :ro.

## Pendências / pedidos
- **dados**: `receitas_candidatos` sem `sq_candidato_doador` (transferências entre candidatos não abatidas); sem `municipios_extra` (AMC = município, desmembrados não agregados) nem `locais_h3`/`votos_local` (H3 → 503); `ds_situacao_candidatura` nulo em 2026.
- **analise**: aceitar `ESTIMÁVEL` na `financeiro` (TODO em `duckdb.py`); docstring diz que pagas não trazem candidato, mas trazem `sq_candidato`.
- `packages/etl/tests/test_processar.py::test_cpf_nunca_toca_processed` falha nesta branch (fora do meu território; branch defasada do etl da main).
- `make lint` falha no web por falta de `node_modules` (ambiente). Python: ruff, mypy ok; apps/api 97 % de cobertura.

## Diff proposto do Makefile (orquestrador)
```make
dev:
	@trap 'kill 0' INT TERM; \
	ELEICOES_DIR_DADOS=$${ELEICOES_DIR_DADOS:-data/processed} uv run uvicorn api.main:app_producao --factory --reload --port 8000 & \
	(cd apps/web && pnpm dev) & wait
```
(o antigo `api.main:app` não existe; é `app_producao --factory`.)

## Como verificar
`ELEICOES_DIR_DADOS=<processed> uv run uvicorn api.main:app_producao --factory --port 8000` e `uv run python apps/api/scripts/smoke.py`; `uv run pytest apps/api`.

## Avisos da conferência T-A04
- Presidente: munzona traz UFs reais; o que ficava só em `BR` é a candidatura (`sg_uf='BR'`). `candidaturas(uf=X, cargo=PRESIDENTE)` agora inclui `BR` (antes zerava o cargo); fixture e teste cobrem. A API nunca soma arquivos por UF.
- Legenda: a API usa só votos nominais (`qt_votos_nominais_validos`); não consome `qt_votos_leg_validos`, então não há risco de legenda parcial em 2022. Quem for expor legenda deve somar leg_validos + nom_convr_leg_validos.
- Custo por voto: descrição OpenAPI dos campos `despesa_*` e `custo_voto_*` diz que exclui repasses a outros candidatos/partidos.
