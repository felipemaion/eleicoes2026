"""Cola da CLI: credenciais do ``.env`` e conferência do token antes de gastar chamadas."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from etl.redes.meta import ClienteMeta, aviso_de_vencimento


def carregar_env(caminho: Path) -> dict[str, str]:
    """Pares ``CHAVE=valor`` do ``.env`` por baixo do ambiente (o ambiente vence).

    Só devolve; nunca imprime valores — o token não pode aparecer em log.
    """
    valores: dict[str, str] = {}
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            texto = linha.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            chave, _, valor = texto.partition("=")
            valores[chave.strip()] = valor.strip().strip("\"'")
    return {**valores, **{k: v for k, v in os.environ.items() if k in valores}}


def conferir_token(cliente: ClienteMeta, env: dict[str, str], hoje: date) -> None:
    """Avisa (stderr) se o token vence em ≤15 dias; vencido/inválido levanta ``ErroMeta``."""
    app_id, segredo = env.get("META_APP_ID"), env.get("META_APP_SECRET")
    if not app_id or not segredo:
        print(
            "AVISO: sem META_APP_ID/META_APP_SECRET — validade do token não conferida",
            file=sys.stderr,
        )
        return
    vence = cliente.validade_token(app_id, segredo)
    if vence is not None and (aviso := aviso_de_vencimento(vence, hoje)):
        print(f"AVISO: {aviso}", file=sys.stderr)
