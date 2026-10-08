"""IPCA (BCB SGS 433): JSON bruto → ``ipca`` Parquet (``mes``, ``variacao``, ``indice``).

SGS 433 é a **variação % mensal**, não um índice. ``indice`` acumula a partir de 100 em
dez/1979 (primeiro mês da série = 1980-01); o fator entre dois meses é
``indice[base] / indice[origem]``. Mês faltando, repetido ou valor ilegível falha alto.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import polars as pl
from contratos import CONTRATOS, validar

from etl.fontes.catalogo import alvos
from etl.processar import ErroProcessamento

IPCA = CONTRATOS["ipca"]


def _mes_seguinte(ano: int, mes: int) -> tuple[int, int]:
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def ler_serie(caminho: Path) -> pl.DataFrame:
    """Lê o JSON do SGS e devolve ``mes``/``variacao``/``indice`` ordenados e contínuos."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        pares = [(datetime.strptime(r["data"], "%d/%m/%Y"), float(r["valor"])) for r in bruto]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ErroProcessamento(f"{caminho}: série IPCA ilegível ({e})") from e
    if not pares:
        raise ErroProcessamento(f"{caminho}: série IPCA vazia")
    pares.sort()
    meses = [(d.year, d.month) for d, _ in pares]
    esperado = meses[0]
    for m in meses:
        if m != esperado:
            raise ErroProcessamento(f"IPCA: esperado {esperado[0]}-{esperado[1]:02d}, veio {m}")
        esperado = _mes_seguinte(*m)
    indice, acumulado = [], 100.0
    for _, v in pares:
        acumulado *= 1 + v / 100
        indice.append(acumulado)
    return pl.DataFrame(
        {
            "mes": [f"{a:04d}-{m:02d}" for a, m in meses],
            "variacao": [v for _, v in pares],
            "indice": indice,
        },
        schema=IPCA.schema(),
    )


def processar_ipca(raiz_raw: Path, raiz_proc: Path) -> Path:
    """JSON bruto do catálogo → ``processed/ipca/ipca.parquet`` (validado, publicação atômica)."""
    [alvo] = alvos(2022, ["ipca"])
    origem = raiz_raw / alvo.destino
    if not origem.exists():
        raise ErroProcessamento(f"{origem} não existe; rode `etl baixar --fonte ipca` antes")
    serie = ler_serie(origem)
    validar(serie, IPCA)
    n_origem = len(json.loads(origem.read_text(encoding="utf-8")))
    if serie.height != n_origem:
        raise ErroProcessamento(f"IPCA: {n_origem} registros na origem × {serie.height} na saída")
    destino = raiz_proc / "ipca" / "ipca.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    try:
        serie.write_parquet(temporario)
        os.replace(temporario, destino)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise
    return destino
