# Alvos do Eleicoes2026. Alvos de pacote passam a funcionar quando o pacote é criado (ver docs/plano.md).
.PHONY: setup test lint etl dev openapi agentes relatorio check-tooling

setup:
	git config core.hooksPath .githooks
	uv sync
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm install) || true

test:
	uv run pytest
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm test) || true

lint:
	uv run ruff check .
	uv run ruff format --check .
	@[ -f apps/web/package.json ] && (cd apps/web && pnpm lint && pnpm typecheck) || true

check-tooling:
	uv run pytest scripts/tests

etl:
	uv run etl baixar --ano $(ANO) && uv run etl processar --ano $(ANO)

dev:
	@echo "API: uv run uvicorn api.main:app --reload --port 8000 | web: cd apps/web && pnpm dev"

openapi:
	uv run python -m api.openapi > docs/api/openapi.json

agentes:
	./scripts/dev-env.sh

relatorio:
	./scripts/ledger.py relatorio
