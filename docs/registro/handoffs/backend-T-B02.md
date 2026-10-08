# Handoff — backend T-B02 (contrato e endpoints de domínio)

Branch `feat/backend-endpoints` (sobre `origin/main` 2e4ad84). Commits: `test:` (vermelho) → `feat:`.

## O que foi feito
- **8 endpoints GET** sob `/api` (rotas finas em `rotas/dominio.py`, regra em `servicos/*`):
  `/grupos`, `/candidatos`, `/candidatos/{ano}/{sq}`, `/mapa`, `/mapa/pontos`, `/gastos`,
  `/comparativo`, `/municipios/{cd}`. Modelos pydantic com exemplos; `docs/api/openapi.json` regenerado.
- **Repositório DuckDB alinhado aos contratos reais (PR #29)**: views sobre
  `<dir>/<dataset>/ano=AAAA/*.parquet` — `consulta_cand`, `votacao_candidato_munzona`
  (votos = `qt_votos_nominais_validos`, voto em trânsito somado), `detalhe_votacao_munzona`
  (aptos = `qt_aptos`, válidos = `qt_total_votos_validos`), `eleitorado_local_votacao`,
  `municipio_tse_ibge`. Turno 1. `dt_geracao` = máx. da coluna `dt_geracao` dos datasets (data
  ISO, ex. `2026-10-06`) — não vem mais do manifesto. `manifesto.json` é opcional (só
  `tp_prestacao_contas` por ano → selo "contas parciais").
- `Repositorio` (Protocol) + `RepositorioDuckDB` + `RepositorioMemoria` (testes de serviço).
- `servicos/adaptador_indicadores.py` = única fonte das fórmulas, **`# TODO(T-A02)`**: penetração,
  % válidos, receitas por fonte, custo por voto, IPCA, evolução por AMC. Testado contra os vetores
  JSON da spec (`penetracao`, `pct_validos`, `receitas`, `custo_por_voto`, `deflacao_ipca`, `evolucao`).
- ETag fraco + `Cache-Control: public, max-age=300` a partir do `dt_geracao`; 304 com
  `If-None-Match`; erros e `/api/health` sem ETag.
- Erros de domínio: `{"detail": {"codigo", "mensagem"}}` (404 recurso, 422 combinação inválida);
  `DadosIndisponiveis` → 503 sem detalhes.
- Grupo por partido sempre amarrado ao ano do grupo (nº 14 era PTB em 2022; teste cobre).

## Decisões
- Enums locais em `api/dominio.py` (`# TODO(T-D02)`: mover p/ `contratos` quando publicar). Cargo =
  `ds_cargo` em maiúsculas, igual ao `/meta`.
- `/mapa`: exatamente um entre `grupo` e `sq_candidato`; `uf` obrigatória em `zona`/`h3`;
  `pct_validos` não existe em H3 (422); município com aptos e sem voto = `0.0`, sem aptos = `null`.
  `escala_sugerida.quebras` = quintis **dos valores da própria resposta** (spec §8.2 pede quintis
  2022+2026 sem `n_baixo` — o front deve fixar as quebras entre anos, ou peço isso à `analise`).
- `/comparativo`: Senado → 422 (spec §1.8). `mesmos_candidatos` por `pessoa_id` (nunca exposto).
- Valores de 2022 deflacionados set/2022→set/2026 (`base_ipca` na resposta). IPCA ausente → 503
  (sem fallback); **o IPCA de set/2026 só sai ~09/10/2026**.

## Pendências / precisa do `dados` (tabelas provisórias, formato flat `<dir>/<nome>.parquet`)
`receitas`, `despesas` (por candidato×rótulos; despesa contratada e paga já ligadas por
candidato), `ipca` (`mes`,`variacao`), `municipios_extra` (`cd_mun_ibge`,`cd_amc`,`area_km2`),
`locais_h3` (+`h3` por local), `votos_local` (votos por local; sem isso `/mapa nivel=h3` e
`/mapa/pontos` dão 503). Sem `municipios_extra`, AMC = município (desmembrados **não** agregados)
e `votos_por_km2` = null. `votacao_partido_munzona` e `consulta_vagas` ainda sem uso (QE/legenda
não expostos nesta tarefa). Fixtures são projeção das colunas lidas, não passam pelo validador de
`contratos`. `/gastos` não exclui `outros_candidatos` com doador do grupo (falta doador no dado).
Rate limit simples não implementado (fora do brief).

## Como verificar
```
uv run python apps/api/scripts/gerar_fixture.py    # recria apps/api/tests/fixtures
make lint && uv run pytest --cov --cov-fail-under=85   # 179 passed, apps/api 97%
make openapi && git diff --exit-code docs/api/openapi.json
```
`make test` falha neste worktree só no passo web (sem `node_modules`; fora do meu território).
