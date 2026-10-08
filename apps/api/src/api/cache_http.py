"""ETag e Cache-Control derivados do DT_GERACAO dos dados; 304 com If-None-Match.

O ETag é fraco (`W/`) porque o gzip reescreve os bytes.
Depende de (dt_geracao, versão do código, URL):
enquanto nem os dados nem o código mudam, a mesma consulta devolve a mesma resposta.
A versão do código (sha do build + hash do OpenAPI) invalida o cache do navegador num deploy
que muda o formato da resposta sem mudar o DT_GERACAO.
"""

import hashlib

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from api.repositorio.base import Repositorio

_SEM_CACHE = {"/api/health"}  # gate de deploy: sempre ao vivo


def _etag(dt_geracao: str, versao: str, request: Request) -> str:
    chave = f"{dt_geracao}|{versao}|{request.url.path}|{request.url.query}"
    return f'W/"{hashlib.sha256(chave.encode()).hexdigest()[:20]}"'


def _casa(cabecalho: str | None, etag: str) -> bool:
    if cabecalho is None:
        return False
    candidatos = {p.strip() for p in cabecalho.split(",")}
    return "*" in candidatos or etag in candidatos


def instalar_cache(app: FastAPI, max_age: int, versao: str) -> None:
    """Registra o middleware de cache condicional nos GET de /api (exceto health).

    `versao` (build + hash do OpenAPI) entra no ETag.
    """
    controle = f"public, max-age={max_age}"

    @app.middleware("http")
    async def cache_condicional(request: Request, call_next: RequestResponseEndpoint) -> Response:
        repo: Repositorio | None = getattr(request.app.state, "repositorio", None)
        if (
            request.method != "GET"
            or not request.url.path.startswith("/api/")
            or request.url.path in _SEM_CACHE
            or repo is None
        ):
            return await call_next(request)
        etag = _etag(repo.dt_geracao(), versao, request)
        if _casa(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": controle})
        resposta = await call_next(request)
        if resposta.status_code == 200:
            resposta.headers["ETag"] = etag
            resposta.headers["Cache-Control"] = controle
        return resposta
