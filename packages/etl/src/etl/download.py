"""Download idempotente com escrita atômica, retry limitado e manifesto."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import httpx

from etl.fontes.catalogo import Alvo
from etl.manifesto import Entrada, Manifesto

TENTATIVAS = 4
BACKOFF_BASE_S = 1.0
CHUNK = 1024 * 1024
RETRY_AFTER_MAX_S = 120.0
REPETIVEIS = frozenset({408, 429})


class DownloadError(RuntimeError):
    """Falha definitiva de download (HTTP 4xx/5xx esgotado ou rede)."""

    def __init__(
        self, mensagem: str, status: int | None = None, retry_after: float | None = None
    ) -> None:
        super().__init__(mensagem)
        self.status = status
        self.retry_after = retry_after


class Resultado(StrEnum):
    """O que aconteceu com um alvo."""

    BAIXADO = "baixado"
    INALTERADO = "inalterado"


@dataclass(frozen=True)
class Baixador:
    """Baixa alvos para ``raiz`` registrando em ``manifesto``."""

    raiz: Path
    manifesto: Manifesto
    cliente: httpx.Client
    dormir: Callable[[float], None] = time.sleep
    agora: Callable[[], datetime] = lambda: datetime.now(UTC)

    def baixar(self, alvo: Alvo, *, forcar: bool = False) -> Resultado:
        """Baixa ``alvo`` salvo se o servidor indicar que nada mudou."""
        destino = self.raiz / alvo.destino
        anterior = self.manifesto.obter(alvo.url)
        if not forcar and anterior and destino.exists() and self._inalterado(alvo, anterior):
            return Resultado.INALTERADO
        return self._baixar(alvo, destino, anterior)

    def _inalterado(self, alvo: Alvo, anterior: Entrada) -> bool:
        """Compara validadores HTTP; sem validadores, decide pelo sha256 após baixar."""
        if not (anterior.etag or anterior.last_modified):
            return False
        try:
            resp = self._com_retry(lambda: self.cliente.head(alvo.url, follow_redirects=True), alvo)
        except DownloadError:
            return False  # HEAD bloqueado/instável: o GET decide (por sha256)
        campo, valor = (
            ("etag", anterior.etag) if anterior.etag else ("last-modified", anterior.last_modified)
        )
        atual: str | None = resp.headers.get(campo)
        return atual == valor

    def _baixar(self, alvo: Alvo, destino: Path, anterior: Entrada | None) -> Resultado:
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".part")
        parcial.unlink(missing_ok=True)  # refaz do zero: nunca confia em resto de execução anterior

        def tentar() -> tuple[httpx.Headers, str, int]:
            sha = hashlib.sha256()
            total = 0
            with self.cliente.stream("GET", alvo.url, follow_redirects=True) as resp:
                self._checar(resp, alvo)
                with parcial.open("wb") as f:
                    for pedaco in resp.iter_bytes(CHUNK):
                        f.write(pedaco)
                        sha.update(pedaco)
                        total += len(pedaco)
                    f.flush()
                    os.fsync(f.fileno())  # dado em disco antes do rename atômico
                esperado = resp.headers.get("content-length")
                # Content-Length conta bytes no fio (pré-gzip): comparar com o bruto recebido.
                if esperado is not None and int(esperado) != resp.num_bytes_downloaded:
                    raise httpx.ReadError(
                        f"truncado: {resp.num_bytes_downloaded} de {esperado} bytes"
                    )
                return resp.headers, sha.hexdigest(), total

        try:
            headers, sha256, total = self._com_retry(tentar, alvo)
        except (OSError, httpx.HTTPError) as e:
            parcial.unlink(missing_ok=True)
            if isinstance(e, DownloadError):
                raise
            raise DownloadError(f"{type(e).__name__} em {alvo.url}: {e}") from e
        except BaseException:
            parcial.unlink(missing_ok=True)
            raise
        mudou = anterior is None or anterior.sha256 != sha256 or not destino.exists()
        if mudou:
            parcial.replace(destino)
        else:
            parcial.unlink()
        self.manifesto.registrar(
            Entrada(
                url=alvo.url,
                caminho=alvo.destino,
                sha256=sha256,
                bytes=total,
                baixado_em=self.agora().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                etag=headers.get("etag"),
                last_modified=headers.get("last-modified"),
                dt_geracao=anterior.dt_geracao if anterior and not mudou else None,
            )
        )
        return Resultado.BAIXADO if mudou else Resultado.INALTERADO

    def verificar(self, alvo: Alvo) -> str:
        """Recalcula o sha256 local: ``ok`` | ``ausente`` | ``corrompido`` (sem rede)."""
        entrada = self.manifesto.obter(alvo.url)
        destino = self.raiz / alvo.destino
        if entrada is None or not destino.exists():
            return "ausente"
        sha = hashlib.sha256()
        with destino.open("rb") as f:
            while pedaco := f.read(CHUNK):
                sha.update(pedaco)
        return "ok" if sha.hexdigest() == entrada.sha256 else "corrompido"

    @staticmethod
    def _checar(resp: httpx.Response, alvo: Alvo) -> None:
        if resp.status_code >= 400:
            raise DownloadError(
                f"HTTP {resp.status_code} em {alvo.url}",
                resp.status_code,
                _retry_after(resp.headers.get("retry-after")),
            )

    def _com_retry[T](self, op: Callable[[], T], alvo: Alvo) -> T:
        """Executa ``op`` com backoff exponencial; 4xx não é repetido."""
        ultimo: Exception | None = None
        for n in range(TENTATIVAS):
            try:
                resp = op()
                if isinstance(resp, httpx.Response):
                    self._checar(resp, alvo)
                return resp
            except DownloadError as e:
                if e.status is not None and e.status < 500 and e.status not in REPETIVEIS:
                    raise
                ultimo = e
                espera = e.retry_after
            except httpx.TransportError as e:
                ultimo = e
                espera = None
            except (
                httpx.HTTPError
            ) as e:  # redirecionamentos demais, decodificação: não adianta repetir
                raise DownloadError(f"{type(e).__name__} em {alvo.url}: {e}") from e
            if n < TENTATIVAS - 1:
                self.dormir(espera if espera is not None else BACKOFF_BASE_S * 2**n)
        raise DownloadError(
            f"falha após {TENTATIVAS} tentativas em {alvo.url}: {ultimo}"
        ) from ultimo


def _retry_after(valor: str | None) -> float | None:
    """Interpreta ``Retry-After`` em segundos (datas HTTP são ignoradas), com teto."""
    if valor is None or not valor.strip().isdigit():
        return None
    return min(float(valor), RETRY_AFTER_MAX_S)
