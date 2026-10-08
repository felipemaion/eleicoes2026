# Alvos do Eleicoes2026. Alvos de pacote passam a funcionar quando o pacote é criado (ver docs/plano.md).
.PHONY: setup test lint etl publicar-dados dev openapi agentes relatorio check-tooling

setup:
	git config core.hooksPath .githooks
	uv sync
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm install) || true

test:
	uv run pytest --cov --cov-fail-under=80
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm test) || true

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy packages/contratos/src packages/indicadores/src packages/etl/src apps/api/src
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm lint && pnpm typecheck) || true

check-tooling:
	uv run pytest scripts/tests

etl:
	uv run etl baixar --ano $(ANO) && uv run etl processar --ano $(ANO) && uv run etl geo

publicar-dados:
	./scripts/publicar-dados.sh $(DIR)

dev:
	@trap 'kill 0' INT TERM; \
	ELEICOES_VERSAO_APP=$${ELEICOES_VERSAO_APP:-dev} ELEICOES_DIR_DADOS=$${ELEICOES_DIR_DADOS:-data/processed} uv run uvicorn api.main:app_producao --factory --reload --port 8000 & \
	(cd apps/web && pnpm dev) & wait

openapi:
	uv run python -m api.openapi > docs/api/openapi.json

agentes:
	./scripts/dev-env.sh

relatorio:
	./scripts/ledger.py relatorio
