"""Fábrica da aplicação FastAPI."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.cache_http import instalar_cache
from api.cache_servico import CacheLRU
from api.config import VERSAO, Settings, obter_settings
from api.erros import ErroDominio
from api.repositorio.base import DadosIndisponiveis
from api.repositorio.duckdb import RepositorioDuckDB
from api.rotas import dominio, meta, saude
from api.servicos.grupos import carregar_catalogo
from api.servicos.meta import carregar_grupos

logger = logging.getLogger(__name__)


def criar_app(settings: Settings | None = None) -> FastAPI:
    """Monta a app; `settings` explícito facilita testes."""
    cfg = settings or obter_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.grupos = carregar_grupos(cfg.arquivo_grupos)
        app.state.cache = CacheLRU(cfg.cache_capacidade)
        app.state.catalogo = carregar_catalogo(cfg.arquivo_grupos, cfg.raiz_repositorio)
        app.state.repositorio = None
        try:
            app.state.repositorio = RepositorioDuckDB(cfg.dir_dados, threads=cfg.threads)
        except DadosIndisponiveis as erro:
            # Não derruba o processo: /api/health responde 503 e o deploy reverte.
            logger.error("dados indisponíveis: %s", erro)
        try:
            yield
        finally:
            if app.state.repositorio is not None:
                app.state.repositorio.fechar()

    app = FastAPI(
        title="Eleicoes2026 API",
        version=VERSAO,
        description="Dados e indicadores eleitorais (somente leitura).",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware, allow_origins=cfg.cors_origens, allow_methods=["GET"], allow_headers=[]
    )
    instalar_cache(app, cfg.cache_max_age)
    app.include_router(saude.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")
    app.include_router(dominio.router, prefix="/api")

    @app.exception_handler(ErroDominio)
    async def _erro_dominio(_: Request, erro: ErroDominio) -> JSONResponse:
        corpo = {"detail": {"codigo": erro.codigo, "mensagem": erro.mensagem}}
        return JSONResponse(corpo, status_code=erro.status)

    @app.exception_handler(DadosIndisponiveis)
    async def _dados_indisponiveis(_: Request, erro: DadosIndisponiveis) -> JSONResponse:
        # Detalhe só no log: caminhos/SQL internos não vão ao cliente.
        logger.error("dados indisponíveis: %s", erro)
        return JSONResponse({"detail": {"codigo": "dados_indisponiveis"}}, status_code=503)

    return app


def app_producao() -> FastAPI:
    """Entrypoint uvicorn (`--factory`)."""
    return criar_app()
