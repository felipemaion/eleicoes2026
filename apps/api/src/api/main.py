"""Fábrica da aplicação FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.config import VERSAO, Settings, obter_settings
from api.repositorio.base import DadosIndisponiveis
from api.repositorio.duckdb import RepositorioDuckDB
from api.rotas import meta, saude
from api.servicos.meta import carregar_grupos


def criar_app(settings: Settings | None = None) -> FastAPI:
    """Monta a app; `settings` explícito facilita testes."""
    cfg = settings or obter_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.grupos = carregar_grupos(cfg.arquivo_grupos)
        app.state.repositorio = None
        app.state.erro_dados = ""
        try:
            app.state.repositorio = RepositorioDuckDB(cfg.dir_dados, threads=cfg.threads)
        except DadosIndisponiveis as erro:
            # Não derruba o processo: /api/health responde 503 e o deploy reverte.
            app.state.erro_dados = str(erro)
        yield
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
    app.include_router(saude.router, prefix="/api")
    app.include_router(meta.router, prefix="/api")
    return app


def app_producao() -> FastAPI:
    """Entrypoint uvicorn (`--factory`)."""
    return criar_app()
