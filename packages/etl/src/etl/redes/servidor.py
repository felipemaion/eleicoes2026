"""Coleta diária de redes no servidor (T-D09, ADR 0008).

Entrada ``redes_candidatos`` em ``datasets`` (somente leitura); a série vive em ``saida`` e só
acumula. A coleta trabalha numa cópia em ``saida/.novo`` e promove por ``os.replace`` só ao
terminar sem erro — falha no meio nunca toca a série anterior (insubstituível: dia perdido é
dado perdido). Cada tentativa deixa ``status.json`` para a API e para o alerta.

Códigos de saída: 0 ok · 1 erro (token, app bloqueado, dados) · 3 limite de chamadas persistente
· 4 coleta ok, mas o token vence em breve (aviso para o alerta do agendador). Exceção não
prevista grava ``status.json`` de erro e é relançada (traceback, saída ≠ 0).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from contratos import ContratoViolado

from etl.redes.coleta import coletar
from etl.redes.meta import ClienteMeta, ErroLimite, ErroMeta

ARQUIVOS_DA_SERIE = ("redes_posts.parquet", "redes_perfis.parquet", "manifesto.json")
"""Ordem de promoção: o manifesto, que a API usa como versão, por último."""
EXIT_OK, EXIT_ERRO, EXIT_LIMITE, EXIT_AVISO = 0, 1, 3, 4


@dataclass(frozen=True)
class ConfigServidor:
    """Caminhos e política de retomada; vêm de variáveis de ambiente (ver ``de_ambiente``)."""

    datasets: Path
    saida: Path
    ano: int = 2026
    tentativas: int = 10
    espera_s: float = 3600
    aviso_dias: int = 14

    @classmethod
    def de_ambiente(cls, env: dict[str, str]) -> ConfigServidor:
        """Lê ``ELEICOES_DIR_*`` e ``REDES_*`` do ambiente (padrões = caminhos do contêiner)."""
        return cls(
            datasets=Path(env.get("ELEICOES_DIR_DATASETS", "/datasets")),
            saida=Path(env.get("ELEICOES_DIR_SAIDA", "/saida")),
            ano=int(env.get("REDES_ANO", "2026")),
            tentativas=int(env.get("REDES_TENTATIVAS", "10")),
            espera_s=float(env.get("REDES_ESPERA_S", "3600")),
            aviso_dias=int(env.get("REDES_AVISO_DIAS", "14")),
        )


def _gravar_status(
    saida: Path, *, inicio: datetime, fim: datetime, resultado: str, motivo: str | None, perfis: int
) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    corpo = {
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "resultado": resultado,
        "motivo": motivo,
        "perfis_coletados": perfis,
        "coletado_em": fim.isoformat(),
    }
    tmp = saida / "status.json.tmp"
    tmp.write_text(json.dumps(corpo, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, saida / "status.json")


def _motivo_curto(e: BaseException, limite: int = 300) -> str:
    """Tipo + mensagem, truncada: o status.json é lido pela API e não deve carregar traceback."""
    texto = f"{type(e).__name__}: {e}"
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _preparar_area(saida: Path) -> Path:
    """Área de trabalho nova com cópia da série atual: a coleta acrescenta, nunca recria."""
    area = saida / ".novo"
    shutil.rmtree(area, ignore_errors=True)
    (area / "redes").mkdir(parents=True)
    for nome in ARQUIVOS_DA_SERIE:
        if (saida / nome).exists():
            shutil.copy2(saida / nome, area / "redes" / nome)
    return area


def _promover(area: Path, saida: Path) -> None:
    """``os.replace`` por arquivo (mesmo filesystem ⇒ atômico); nunca expõe Parquet pela metade."""
    for nome in ARQUIVOS_DA_SERIE:
        origem = area / "redes" / nome
        if origem.exists():
            os.replace(origem, saida / nome)


def _motivo_do_token(
    cliente: Any, env: dict[str, str], agora: datetime, aviso_dias: int
) -> str | None:
    """Falha alto se o token venceu/é inválido; devolve texto de aviso a ≤ ``aviso_dias``."""
    app_id, segredo = env.get("META_APP_ID"), env.get("META_APP_SECRET")
    if not app_id or not segredo:
        print(
            "AVISO: sem META_APP_ID/META_APP_SECRET — validade do token não conferida",
            file=sys.stderr,
        )
        return None
    vence = cliente.validade_token(app_id, segredo)
    if vence is None:
        return None
    dias = (vence.date() - agora.date()).days
    if dias < 0:
        raise ErroMeta(f"o token venceu em {vence:%d/%m/%Y} — gere outro (ADR 0008)")
    if dias <= aviso_dias:
        return f"o token vence em {dias} dia{'' if dias == 1 else 's'} ({vence:%d/%m/%Y}) — renove"
    return None


def executar(
    cfg: ConfigServidor,
    env: dict[str, str],
    *,
    cliente: Any = None,
    coletar_fn: Callable[..., Any] = coletar,
    agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Roda a coleta do dia com retomada por limite, promoção atômica e ``status.json``."""
    inicio = agora()
    perfis_total = 0

    def encerrar(codigo: int, resultado: str, motivo: str | None) -> int:
        _gravar_status(
            cfg.saida,
            inicio=inicio,
            fim=agora(),
            resultado=resultado,
            motivo=motivo,
            perfis=perfis_total,
        )
        if motivo:
            print(
                f"{'AVISO' if codigo == EXIT_AVISO else 'FALHA'} redes-servidor: {motivo}",
                file=sys.stderr,
            )
        return codigo

    arquivo = cfg.datasets / "redes_candidatos" / f"ano={cfg.ano}" / "redes_candidatos.parquet"
    if not env.get("META_TOKEN"):
        return encerrar(EXIT_ERRO, "erro", "META_TOKEN ausente do ambiente")
    if not arquivo.exists():
        return encerrar(EXIT_ERRO, "erro", f"entrada redes_candidatos ausente: {arquivo}")
    area = _preparar_area(cfg.saida)
    try:
        cliente = cliente or ClienteMeta(env["META_TOKEN"])
        aviso = _motivo_do_token(cliente, env, inicio, cfg.aviso_dias)
        candidatos = pl.read_parquet(arquivo)
        conta = cliente.conta_instagram()
        limitado = False
        for tentativa in range(1, cfg.tentativas + 1):
            try:
                stats = coletar_fn(
                    cliente, conta, candidatos,
                    raiz_raw=area / "raw", raiz_processed=area, agora=agora,
                )  # fmt: skip
            except ErroLimite as e:
                limitado = True
                print(
                    f"limite de chamadas (tentativa {tentativa}/{cfg.tentativas}): {e}",
                    file=sys.stderr,
                )
                if tentativa < cfg.tentativas:
                    dormir(cfg.espera_s)
                continue
            perfis_total += sum(stats.get("perfis", {}).values())
            limitado = False
            break
    except (ErroMeta, ContratoViolado, OSError) as e:
        shutil.rmtree(area, ignore_errors=True)
        return encerrar(EXIT_ERRO, "erro", str(e))
    except Exception as e:
        # Erro não previsto (ComputeError, KeyError, JSON malformado…): sem isto o processo
        # morre sem status.json e a API não distingue "falhou" de "ainda rodando". Registra e
        # relança — o código de saída ≠ 0 aciona o OnFailure do agendador.
        shutil.rmtree(area, ignore_errors=True)
        try:
            encerrar(EXIT_ERRO, "erro", _motivo_curto(e))
        except Exception as falha_status:
            # Gravar o status é o recurso de último caso; se ele também falhar, a causa que
            # importa é a original — registra a segunda falha e deixa a primeira propagar.
            print(f"FALHA ao gravar status.json: {falha_status!r}", file=sys.stderr)
        raise
    # Limite persistente: o que foi gravado antes do corte é válido (contrato conferido em
    # `coletar`) e é promovido; a próxima execução continua de onde parou.
    _promover(area, cfg.saida)
    shutil.rmtree(area, ignore_errors=True)
    if limitado:
        return encerrar(
            EXIT_LIMITE, "limite", f"limite de chamadas persistiu em {cfg.tentativas} tentativas"
        )
    return encerrar(EXIT_AVISO if aviso else EXIT_OK, "ok", aviso)
