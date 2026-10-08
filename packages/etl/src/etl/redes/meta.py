"""Cliente mínimo da Instagram Graph API — endpoint Business Discovery (ADR 0008).

Regras que moldam o código:

* O token vai no cabeçalho ``Authorization``, **nunca** na URL (exceção: ``debug_token`` só
  aceita ``input_token`` na query). Mensagens de erro nunca carregam URL nem cabeçalhos.
* Conta pessoal ou inexistente não derruba a coleta: vira :class:`PerfilIndisponivel` com o
  status a gravar. Token/permissão inválidos **falham alto** (:class:`ErroMeta`).
* Limite de chamadas (códigos 4/17/32/613/80004): backoff exponencial; se persistir,
  :class:`ErroLimite` — a coleta grava o que tem e pode ser retomada (o cache evita refazer).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import httpx

VERSAO_API = "v26.0"
BASE = "https://graph.facebook.com"
LIMITE_MIDIAS = 50  # por página; a API aceita até 100, mas 50 mantém a resposta leve
CAMPOS_PERFIL = "username,name,biography,followers_count,follows_count,media_count"
CAMPOS_MIDIA = "id,timestamp,media_type,media_product_type,like_count,comments_count,permalink"
CODIGOS_LIMITE = frozenset({4, 17, 32, 613, 80004})
CODIGOS_FATAIS = frozenset({190, 102, 10, 458, 459, 460, 463, 467}) | frozenset(range(200, 300))
CODIGOS_PERFIL_INDISPONIVEL = frozenset({110, 100})
USO_MAXIMO = 95  # % do limite do app a partir do qual a próxima chamada espera
AVISO_DIAS = 15
_USERNAME = re.compile(r"[a-z0-9._]{1,30}")
_NAO_COMERCIAL = re.compile(r"comercial|criador|business|creator", re.IGNORECASE)


class ErroMeta(RuntimeError):  # noqa: N818 - nome de domínio
    """Falha que exige ação humana (token, permissão, resposta inesperada)."""


class ErroLimite(ErroMeta):
    """Limite de chamadas persistiu após o backoff: pare, grave o progresso e retome depois."""


class PerfilIndisponivel(Exception):  # noqa: N818 - não é erro: é um resultado esperado
    """Conta pessoal, inexistente ou fora do alcance do Business Discovery."""

    def __init__(self, username: str, status: str) -> None:
        super().__init__(f"{username}: {status}")
        self.username = username
        self.status = status


@dataclass(frozen=True)
class Pagina:
    """Uma página do Business Discovery: perfil + mídias (da mais nova para a mais antiga)."""

    username: str
    seguidores: int | None
    seguindo: int | None
    midias_total: int | None
    midias: list[dict[str, Any]]
    proximo: str | None


def _midia(bruta: dict[str, Any]) -> dict[str, Any]:
    return {
        "media_id": bruta["id"],
        "timestamp": datetime.strptime(bruta["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(UTC),
        "media_type": bruta.get("media_type"),
        "media_product_type": bruta.get("media_product_type"),
        "like_count": bruta.get("like_count"),  # ausente = oculto pelo dono → nulo, não zero
        "comments_count": bruta.get("comments_count"),
        "permalink": bruta.get("permalink"),
    }


@dataclass
class ClienteMeta:
    """Cliente HTTP da Graph API com backoff, contagem de chamadas e token fora da URL."""

    token: str = field(repr=False)
    http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=60.0))
    dormir: Callable[[float], None] = time.sleep
    espera_base: float = 60.0
    # uso do app ≥95%: o contador é de janela móvel de 1 h, então 1 min não adianta
    pausa_uso: float = 300.0
    max_tentativas: int = 5
    chamadas: int = 0
    _pausa_pendente: bool = field(default=False, repr=False)

    def get(
        self, caminho: str, params: dict[str, str], *, bearer: str | None = None
    ) -> dict[str, Any]:
        """GET com backoff nos códigos de limite; devolve o JSON ou levanta :class:`ErroMeta`."""
        for tentativa in range(self.max_tentativas):
            if self._pausa_pendente:
                self._pausa_pendente = False
                self.dormir(self.pausa_uso)
            resposta = self._requisitar(caminho, params, bearer or self.token)
            corpo = _json(resposta)
            self._ler_uso(resposta)
            erro = corpo.get("error")
            if erro is None:
                return corpo
            if int(erro.get("code", 0)) in CODIGOS_LIMITE:
                if tentativa + 1 < self.max_tentativas:
                    self.dormir(self.espera_base * 2**tentativa)
                continue
            raise _traduzir(erro)
        raise ErroLimite(f"limite de chamadas persistiu após {self.max_tentativas} tentativas")

    def _requisitar(self, caminho: str, params: dict[str, str], bearer: str) -> httpx.Response:
        self.chamadas += 1
        try:
            return self.http.get(
                f"{BASE}/{VERSAO_API}/{caminho}",
                params=params,
                headers={"Authorization": f"Bearer {bearer}"},
            )
        except httpx.HTTPError as e:
            # `from None`: a exceção original pode citar a URL (com input_token) no contexto
            raise ErroMeta(f"falha de rede ({type(e).__name__}) em {caminho}") from None

    def _ler_uso(self, resposta: httpx.Response) -> None:
        bruto = resposta.headers.get("x-app-usage")
        if bruto is None:
            return
        try:
            uso = int(json.loads(bruto).get("call_count", 0))
        except (ValueError, TypeError, AttributeError):
            return
        if uso >= USO_MAXIMO:
            self._pausa_pendente = True

    def conta_instagram(self) -> str:
        """Id da conta Instagram ligada ao app, descoberto via ``me/accounts`` (nunca fixo)."""
        dados = self.get("me/accounts", {"fields": "instagram_business_account"})
        for pagina in dados.get("data", []):
            conta = pagina.get("instagram_business_account")
            if conta:
                return str(conta["id"])
        raise ErroMeta("nenhuma página do token tem instagram_business_account vinculado")

    def business_discovery(self, conta_id: str, username: str, cursor: str | None = None) -> Pagina:
        """Perfil + uma página de mídias de ``username`` (cursor = ``after`` da página anterior)."""
        if not _USERNAME.fullmatch(username):
            raise ValueError(f"username inválido para a consulta: {username!r}")
        if cursor is not None and not re.fullmatch(r"[A-Za-z0-9_=\-+/]+", cursor):
            raise ValueError("cursor de paginação inválido")
        depois = f".after({cursor})" if cursor else ""
        midia = f"media.limit({LIMITE_MIDIAS}){depois}{{{CAMPOS_MIDIA}}}"
        campos = f"business_discovery.username({username}){{{CAMPOS_PERFIL},{midia}}}"
        try:
            corpo = self.get(conta_id, {"fields": campos})
        except _ErroApi as e:
            raise self._indisponivel_ou_fatal(username, e) from None
        bd = corpo["business_discovery"]
        media = bd.get("media", {})
        paging = media.get("paging", {})
        return Pagina(
            username=bd["username"],
            seguidores=bd.get("followers_count"),
            seguindo=bd.get("follows_count"),
            midias_total=bd.get("media_count"),
            midias=[_midia(m) for m in media.get("data", [])],
            # a Business Discovery não manda `next`: só `cursors.after`, ausente na última página
            proximo=paging.get("cursors", {}).get("after"),
        )

    @staticmethod
    def _indisponivel_ou_fatal(username: str, e: _ErroApi) -> Exception:
        if e.code in CODIGOS_PERFIL_INDISPONIVEL:
            texto = f"{e.mensagem} {e.mensagem_usuario}"
            status = "nao_comercial" if _NAO_COMERCIAL.search(texto) else "nao_encontrado"
            return PerfilIndisponivel(username, status)
        return ErroMeta(f"Graph API código {e.code}: {e.mensagem}")

    def validade_token(self, app_id: str, app_secret: str) -> datetime | None:
        """Quando o token vence (``debug_token``); ``None`` se não expira. Inválido → erro."""
        corpo = self.get(
            "debug_token", {"input_token": self.token}, bearer=f"{app_id}|{app_secret}"
        )
        dados = corpo["data"]
        if not dados.get("is_valid"):
            raise ErroMeta("token inválido segundo debug_token — gere outro")
        expira = int(dados.get("expires_at", 0))
        return datetime.fromtimestamp(expira, UTC) if expira else None


class _ErroApi(ErroMeta):
    """Erro da API com código, para o chamador decidir entre status e falha."""

    def __init__(self, code: int, mensagem: str, mensagem_usuario: str) -> None:
        super().__init__(f"Graph API código {code}: {mensagem}")
        self.code = code
        self.mensagem = mensagem
        self.mensagem_usuario = mensagem_usuario


def _traduzir(erro: dict[str, Any]) -> ErroMeta:
    code = int(erro.get("code", 0))
    mensagem = str(erro.get("message", ""))
    usuario = str(erro.get("error_user_msg", ""))
    if code in CODIGOS_FATAIS:
        return ErroMeta(f"Graph API código {code}: {mensagem}")
    return _ErroApi(code, mensagem, usuario)


def _json(resposta: httpx.Response) -> dict[str, Any]:
    try:
        corpo = resposta.json()
    except ValueError:
        raise ErroMeta(f"resposta não-JSON da Graph API (HTTP {resposta.status_code})") from None
    if not isinstance(corpo, dict):
        raise ErroMeta("resposta inesperada da Graph API")
    return corpo


def aviso_de_vencimento(vence: datetime, hoje: date) -> str | None:
    """Texto de aviso se faltam ``AVISO_DIAS`` ou menos; token vencido falha alto."""
    dias = (vence.date() - hoje).days
    if dias < 0:
        raise ErroMeta(f"o token venceu em {vence:%d/%m/%Y} — gere outro (ADR 0008)")
    if dias == 0:
        return f"o token vence hoje ({vence:%d/%m/%Y})"
    if dias <= AVISO_DIAS:
        plural = "dia" if dias == 1 else "dias"
        return f"o token vence em {dias} {plural} ({vence:%d/%m/%Y}) — renove"
    return None
