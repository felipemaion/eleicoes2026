"""Fábrica da aplicação FastAPI."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.aquecimento import Aquecimento
from api.cache_http import instalar_cache
from api.cache_servico import CacheLRU
from api.config import VERSAO, Settings, obter_settings
from api.erros import ErroDominio
from api.repositorio.base import DadosIndisponiveis, MemoriaInsuficiente
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
        app.state.cache = CacheLRU(
            cfg.cache_capacidade, cfg.calculos_simultaneos, cfg.espera_vaga_s
        )
        app.state.catalogo = carregar_catalogo(cfg.arquivo_grupos, cfg.raiz_repositorio)
        app.state.repositorio = None
        app.state.aquecimento = None
        try:
            app.state.repositorio = RepositorioDuckDB(
                cfg.dir_dados,
                threads=cfg.threads,
                memory_limit=cfg.duck_memory_limit,
                max_temp_directory_size=cfg.duck_max_temp_directory_size,
                temp_directory=cfg.duck_temp_directory,
            )
            # `uvicorn.error` tem handler em INFO; o logger do módulo não aparece em produção.
            logging.getLogger("uvicorn.error").info(
                "duckdb configuração efetiva: %s", app.state.repositorio.configuracao()
            )
        except DadosIndisponiveis as erro:
            # Não derruba o processo: /api/health responde 503 e o deploy reverte.
            logger.error("dados indisponíveis: %s", erro)
        if cfg.aquecer and app.state.repositorio is not None:
            app.state.aquecimento = Aquecimento(
                app.state.repositorio,
                app.state.catalogo,
                app.state.cache,
                cfg.aquecimento_max_entradas,
            )
            app.state.aquecimento.start()  # segundo plano: o health não espera
        try:
            yield
        finally:
            if app.state.aquecimento is not None:
                app.state.aquecimento.parar()
                app.state.aquecimento.join(timeout=30)  # antes de fechar o DuckDB
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
        cabecalhos = {"Retry-After": "1"} if erro.status == 503 else None
        return JSONResponse(corpo, status_code=erro.status, headers=cabecalhos)

    @app.exception_handler(DadosIndisponiveis)
    async def _dados_indisponiveis(_: Request, erro: DadosIndisponiveis) -> JSONResponse:
        # Detalhe só no log: caminhos/SQL internos não vão ao cliente.
        logger.error("dados indisponíveis: %s", erro)
        return JSONResponse({"detail": {"codigo": "dados_indisponiveis"}}, status_code=503)

    @app.exception_handler(MemoriaInsuficiente)
    async def _memoria_insuficiente(_: Request, erro: MemoriaInsuficiente) -> JSONResponse:
        return responder_memoria_insuficiente(erro)

    return app


def responder_memoria_insuficiente(erro: MemoriaInsuficiente) -> JSONResponse:
    """503 `memoria_insuficiente` com Retry-After; o detalhe do DuckDB fica só no log."""
    logger.error("memória insuficiente no DuckDB: %s", erro)
    return JSONResponse(
        {"detail": {"codigo": "memoria_insuficiente", "mensagem": "memória esgotada; tente já"}},
        status_code=503,
        headers={"Retry-After": "5"},
    )


def app_producao() -> FastAPI:
    """Entrypoint uvicorn (`--factory`)."""
    return criar_app()
