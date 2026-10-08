"""Username do Instagram a partir do texto livre que o candidato digitou no TSE.

O campo ``DS_URL`` do cadastro não é validado: vem URL completa (com ``?igsh=``), ``@handle``,
``INSTAGRAM: handle``, ``handle - instagram``, links de post/canal e até outras redes. Aqui só
sai um username se o texto aponta para **um perfil** inequívoco; o resto vira ``None`` (e é
contado no relatório), nunca um palpite.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

# Regras do Instagram: 1–30 caracteres entre letras, dígitos, ponto e sublinhado.
_USERNAME = re.compile(r"[a-z0-9._]{1,30}")
_INSTAGRAM = r"instagra[mn]"  # "instagran" aparece digitado no cadastro
_HOST = re.compile(rf"(?:https?://)?(?:www\.|m\.)?{_INSTAGRAM}\.com/(?P<resto>[^\s?#]*)")
# Caminhos de `instagram.com/<x>` que não são perfil (post, vídeo, canal, id numérico…).
_NAO_PERFIL = frozenset(
    {
        "p", "reel", "reels", "tv", "stories", "explore", "channel", "uid", "accounts", "direct",
        "about", "legal", "s", "share", "web", "developer", "directory", "challenge", "popular",
    }
)  # fmt: skip
_OUTRAS_REDES = re.compile(
    r"facebook|fb\.com|fb\.me|tiktok|twitter|x\.com|youtube|youtu\.be|kwai|threads\.|"
    r"whatsapp|wa\.me|t\.me|telegram|linkedin|linktr|kwai-video|spotify|pinterest"
)
_SEPARADORES = re.compile(r"[\s:;,()\[\]<>|/\\\"'“”-]+")


def _valido(candidato: str) -> str | None:
    """Normaliza (``@``, ponto final, caixa) e confere o formato de username."""
    nome = candidato.strip().lstrip("@").rstrip(".").lower()
    if not _USERNAME.fullmatch(nome) or nome in _NAO_PERFIL:
        return None
    return nome


def _de_url(texto: str) -> str | None | bool:
    """Username de ``instagram.com/<perfil>``; ``False`` se o texto não tem esse host."""
    casou = _HOST.search(texto)
    if casou is None:
        return False
    segmentos = [s for s in casou.group("resto").split("/") if s]
    if segmentos and segmentos[0] == "_u":  # deep link: instagram.com/_u/<perfil>
        segmentos = segmentos[1:]
    if len(segmentos) != 1:  # raiz sem perfil, ou caminho aninhado (p/…, reel/…, channel/…)
        return None
    return _valido(segmentos[0])


def username_instagram(texto: str) -> str | None:
    """Username normalizado (minúsculo, sem ``@``) se ``texto`` é perfil do Instagram, senão ``None``.

    Aceita URL de perfil e forma solta (``@handle``, ``instagram: handle``). Rejeita post, reel,
    canal, id numérico, nome com espaço e qualquer texto que cite outra rede.
    """
    limpo = unquote(texto).strip().lower()
    if not limpo:
        return None
    cita_instagram = re.search(_INSTAGRAM, limpo) is not None
    if _OUTRAS_REDES.search(limpo):
        return None  # "@fulano (tiktok)" ou link de outra rede: não é Instagram
    if (url := _de_url(limpo)) is not False:
        return url
    # `instagram.com@handle`, `https://instagram@handle`: o arroba cola o host ao perfil
    colado = re.search(rf"{_INSTAGRAM}(?:\.com)?@([^\s/?#]+)", limpo)
    if colado:
        return _valido(colado.group(1))
    # forma solta: tira a palavra "instagram", o esquema e os separadores; sobra o handle
    sobra = re.sub(rf"https?://|www\.|{_INSTAGRAM}(?:\.com)?", " ", limpo)
    fichas = {f for f in _SEPARADORES.split(sobra) if f}
    nomes = {n for f in fichas if (n := _valido(f)) is not None}
    if len(fichas) != 1 or len(nomes) != 1:
        return None  # vazio, "nome sobrenome" ou mais de um candidato a handle
    # sem a palavra "instagram" só vale o `@handle` explícito (evita aceitar domínio solto)
    if not cita_instagram and not limpo.startswith("@"):
        return None
    return nomes.pop()
