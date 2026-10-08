# Handoff backend — T-B06 (pontos 500: locais sem coordenada)

Branch `fix/backend-pontos-sem-coordenada` (não pushada).

## O que fez
- `/api/mapa/pontos`: consulta filtra `lat/lon` nulos (era o `ValidationError` → 500).
- Resposta de `/mapa/pontos` ganha `votos_sem_coordenada` (int) e `pct_votos_sem_coordenada` (%, 2 casas), do recorte inteiro da UF (não só da página).
- `/api/mapa?nivel=h3`: mesmos dois campos (null nos demais níveis). No H3 "sem coordenada" = local sem célula H3 (`h3 IS NULL`), que é o que a rota descarta.
- Novo `Repositorio.votos_sem_coordenada(ano, sqs, uf, por_h3)` (DuckDB; memória levanta `NotImplementedError`, como `pontos`/`votos_h3`).
- Fixture: local SP 3/5001 sem coordenada com 120 votos (`gerar_fixture.py` regenerado; 3 Parquet mudaram). Testes de integração novos em `test_endpoints_dominio.py`.
- `docs/api/openapi.json` regenerado (campos novos, aditivos — não quebram o front).

## Decisões
- Pct sobre votos dos locais que casam com `locais_votacao` da UF; votos sem local cadastrado ficam fora do denominador.
- Recorte vazio → pct 0.0 (sem divisão por zero).

## Pendências
- Frontend: mostrar aviso quando `pct_votos_sem_coordenada` > 5 (e regenerar tipos do OpenAPI).
- Smoke contra produção depois do deploy: `/api/mapa/pontos?ano=2026&grupo=missao_2026&uf=SP&cargo=DEPUTADO%20FEDERAL` deve dar 200.

## Verificar
`uv run pytest apps/api -q`; `uv run mypy apps/api/src`; `make openapi` sem diff. (`make lint` falha no eslint só por falta de `node_modules` neste worktree.)
