# Handoff backend — T-B04 (ajustes pós-deploy)
Branch `feat/backend-pos-deploy` (de `origin/main` 27fba04). 173 testes verdes em `apps/api` + `scripts/tests`;
cobertura de `api` 97%; `ruff` e `mypy --strict` (src) limpos. `eslint` indisponível aqui (sem node_modules).

## O que mudou (contrato — OpenAPI regenerado, **avisar o frontend**)
- `GET /api/candidatos` → novo campo `kpis` (`KpisGrupo`: `votos`, `aptos`, `validos`, `pct_validos`,
  `penetracao`) = grupo como candidato coletivo no recorte. **null sem `cargo`** (nunca soma cargos) ou sem
  candidaturas. Soma por `indicadores.grupos.agregar_grupo`; taxas por `indicadores.desempenho`.
- `CandidatoResumo.indicado: bool` (em `/candidatos` e na ficha): `origem=indicado` no CSV da lista,
  lido no `carregar_catalogo` (`Catalogo.indicados`); listas sem coluna `origem` não marcam ninguém.
- `GET /api/mapa` → `detalhes[chave].nome` (município; também em `IBGE-zona`; null no H3).
- `montar_ficha` agora recebe o `Catalogo` (para `indicado`).

## Aquecimento (`api/aquecimento.py`, `api/servicos/consultas.py`)
- Thread daemon iniciada no `lifespan` após abrir os dados; o health não espera. **Um cálculo por vez**
  (uma vaga do semáforo), 503 → espera 0,5 s e tenta de novo (até 20×).
- Plano: cada grupo × (Brasil, depois UFs com candidatos) × deputado federal/estadual/distrital →
  `/candidatos` e `/gastos`; cada comparação × mesmos recortes do grupo `para` → `/comparativo`.
- Rota e aquecimento chamam as mesmas funções `*_em_cache` (chave idêntica, DRY).
- Orçamento `ELEICOES_AQUECIMENTO_MAX_ENTRADAS` (128 = metade do LRU) para não expulsar entradas quentes;
  `ELEICOES_AQUECER=false` desliga. Falha de consulta é logada + contada (`erros`), nunca engolida.
- Desligamento: `parar()` + `join(30 s)` antes de fechar o DuckDB.
- Nos testes o padrão é `aquecer=False` (conftest, test_saude, b02); `test_pos_deploy.py` liga.

## Smoke
- `apps/api/scripts/smoke.py` envia `User-Agent: eleicoes2026-smoke/1.0` (teste com servidor local).
- **Pendente (não rodei):** `uv run python apps/api/scripts/smoke.py --base https://eleicoes2026.maionesys.com`
  só faz sentido depois do deploy desta branch (os novos campos). Rodar após o merge.

## Pendências / decisões
- Item 4 (classificação de receitas): **T-A07 ainda não entrou**. O `ESTIMÁVEL→ESTIMADO` segue em
  `repositorio/duckdb.py:82-85` (view). Quando a T-A07 chegar, mover a regra para `indicadores.financeiro`
  e apagar o CASE da view — fica para uma T-B05.
- Aquecimento cobre candidatos/gastos/comparativo com os defaults (`limite=200`); `/mapa` não é aquecido
  (combinações demais). Dizer se vale incluir.
- `kpis` usa a soma por município vinda do DuckDB (já Σ dos membros) alimentada em `agregar_grupo` com o
  grupo como entidade única — a lib impõe cargo/turno únicos; não há consulta por candidato.

## Como verificar
`uv run pytest apps/api scripts/tests`; `make openapi` (sem diff); `curl '/api/candidatos?grupo=missao_2026&uf=SP&cargo=DEPUTADO%20FEDERAL'`.
