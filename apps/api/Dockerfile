# syntax=docker/dockerfile:1.7
# API Eleicoes2026 — imagem linux/arm64 (Oracle Ampere A1, ADR 0002). Contexto de build = raiz do
# repositório (workspace uv):  docker buildx build --platform linux/arm64 -f apps/api/Dockerfile .

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder: venv com as deps
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# 1) Só manifestos + lock: a camada de dependências não se invalida a cada mudança de código.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/contratos/pyproject.toml packages/contratos/pyproject.toml
COPY packages/indicadores/pyproject.toml packages/indicadores/pyproject.toml
COPY packages/etl/pyproject.toml packages/etl/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package api --no-install-workspace

# 2) Código dos membros que a API usa (etl fica de fora: só o manifesto resolve o workspace).
COPY apps/api/src apps/api/src
COPY packages/contratos/src packages/contratos/src
COPY packages/indicadores/src packages/indicadores/src
COPY README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package api

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# Definição dos grupos e a lista MBL 2022 (sem CPF) — insumos versionados lidos em runtime.
COPY config/grupos.yaml config/grupos.yaml
COPY data/reference/mbl_2022.csv data/reference/mbl_2022.csv

# Em --no-editable o pacote mora em site-packages: os caminhos não podem ser deduzidos do
# __file__, então vêm do ambiente. Os Parquet entram por volume somente leitura em /datasets.
# Sha do build (deploy.yml passa `--build-arg VERSAO_APP=${{ github.sha }}`): entra no ETag e no
# /api/health. Sem default: a API recusa subir sem ele.
ARG VERSAO_APP
ENV ELEICOES_VERSAO_APP=$VERSAO_APP
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ELEICOES_DIR_DADOS=/datasets \
    ELEICOES_ARQUIVO_GRUPOS=/app/config/grupos.yaml \
    ELEICOES_RAIZ_REPOSITORIO=/app \
    ELEICOES_THREADS=2

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

# Um worker: o DuckDB já usa as 2 threads do teto; mais processos só duplicariam o cache LRU.
CMD ["uvicorn", "api.main:app_producao", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
