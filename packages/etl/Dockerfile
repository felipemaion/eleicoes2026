# syntax=docker/dockerfile:1.7
# Coleta diária de redes no servidor (T-D09, ADR 0008) — linux/arm64. Contexto = raiz do repositório:
#   docker buildx build --platform linux/arm64 -f packages/etl/Dockerfile .
# Só o ETL leve: sem GDAL/tippecanoe (geo roda no Mac). Variáveis lidas: ver `etl redes-servidor --help`.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Manifestos + lock primeiro: a camada de dependências não se invalida a cada mudança de código.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/contratos/pyproject.toml packages/contratos/pyproject.toml
COPY packages/indicadores/pyproject.toml packages/indicadores/pyproject.toml
COPY packages/etl/pyproject.toml packages/etl/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package etl --no-install-workspace

COPY packages/contratos/src packages/contratos/src
COPY packages/etl/src packages/etl/src
COPY README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package etl

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY config config
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ELEICOES_DIR_DATASETS=/datasets \
    ELEICOES_DIR_SAIDA=/saida

# /saida precisa ser gravável por uid 10001 no host (o servidor ajusta o dono de data/redes).
USER app
ENTRYPOINT ["etl"]
CMD ["redes-servidor"]
