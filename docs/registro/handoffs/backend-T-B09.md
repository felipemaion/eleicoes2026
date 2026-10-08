# Handoff backend — T-B09 (UFs por cargo)

**Branch:** `feat/backend-ufs-por-cargo`

## O que foi feito
- `GET /api/candidatos/ufs?ano=&cargo=&grupo=` → `{itens: [{uf, candidaturas}], dt_geracao}`, ordenado por UF.
- Exige `ano` ou `grupo` (o grupo define o ano; `grupo` + `ano` divergentes → 422 `grupo_ano_incompativel`; sem nenhum → 422 `recorte_incompleto`).
- Presidente devolve só `BR`; recorte vazio → lista vazia (200).
- Cache LRU + ETag/Cache-Control pelo `DT_GERACAO`, como as demais rotas.
- OpenAPI regenerado (`docs/api/openapi.json`).

## Decisões
- Sem método novo no `Repositorio`: o serviço (`ufs_disponiveis`, em `servicos/candidatos.py`) conta sobre `repo.candidaturas` / `candidaturas_do_grupo`, reusando a regra de grupo (partido ∪ sqs). Contagem por grupo bate com `n_candidaturas` de `/grupos` (teste).
- Rota `/candidatos/ufs` não colide com `/candidatos/{ano}/{sq}` (segmentos diferentes).

## Pendências
- **Varredura em produção NÃO rodada:** o endpoint ainda não está no deploy. Depois do deploy:
  `uv run python apps/api/scripts/varredura.py --base https://eleicoes2026.maionesys.com` e registrar o resultado
  (a varredura não cobre `/candidatos/ufs` ainda; incluir se quiser).
- `make lint` falha só no eslint do web (`eslint: command not found` — `pnpm install` não feito neste worktree); Python (ruff, mypy) verde.

## Como verificar
`uv run pytest apps/api/tests/test_b09_ufs.py` · suíte API: 538 passed, cobertura 95%.
