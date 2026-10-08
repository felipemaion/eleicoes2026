"""CLI: ``etl baixar --ano 2026 [--fonte ID ...] [--uf SP]``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
from contratos import ContratoViolado

from etl.download import Baixador, DownloadError
from etl.fontes.catalogo import CATALOGO, alvos
from etl.ipca import processar_ipca
from etl.manifesto import Manifesto
from etl.processar import CONTAS, FONTES, ErroProcessamento, processar_fonte


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="etl")
    sub = p.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("baixar", help="baixa fontes oficiais para data/raw")
    b.add_argument("--ano", type=int, required=True)
    b.add_argument("--fonte", action="append", choices=sorted(CATALOGO), help="repetível")
    b.add_argument("--uf", help="restringe fontes por UF (ex.: SP)")
    b.add_argument("--raiz", type=Path, default=Path("data/raw"))
    b.add_argument("--verificar", action="store_true", help="só confere sha256 local (sem rede)")
    b.add_argument("--forcar", action="store_true", help="ignora o cache")
    c = sub.add_parser("processar", help="ZIPs brutos → Parquet validado em data/processed")
    c.add_argument("--ano", type=int, help="obrigatório, salvo com --dataset ipca")
    c.add_argument("--fonte", action="append", choices=sorted(FONTES), help="repetível")
    c.add_argument(
        "--dataset",
        choices=("contas", "ipca"),
        help="contas = receitas + despesas contratadas e pagas; ipca = série SGS 433 (sem ano)",
    )
    c.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    c.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    return p


def _processar(args: argparse.Namespace) -> int:
    manifesto = Manifesto(args.raiz_raw / "manifesto.json")
    sal = os.environ.get("PESSOA_ID_SAL") or None
    falhas = 0
    if args.dataset == "ipca":
        try:
            print(f"processado ipca: {processar_ipca(args.raiz_raw, args.raiz_processed)}")
        except (ErroProcessamento, ContratoViolado) as e:
            print(f"FALHA ipca: {e}", file=sys.stderr)
            return 1
        return 0
    if args.ano is None:
        print("erro: --ano é obrigatório", file=sys.stderr)
        return 2
    selecionadas = list(CONTAS) if args.dataset == "contas" else args.fonte or list(FONTES)
    for fonte in selecionadas:
        try:
            saidas = processar_fonte(
                fonte, args.ano, args.raiz_raw, args.raiz_processed, manifesto=manifesto, sal=sal
            )
        except (ErroProcessamento, ContratoViolado) as e:
            falhas += 1
            print(f"FALHA {fonte}: {e}", file=sys.stderr)
        else:
            print(f"processado {fonte}: {len(saidas)} arquivo(s)")
    return 1 if falhas else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada; devolve o código de saída."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = _parser().parse_args(argv)
    if args.comando == "processar":
        return _processar(args)
    try:
        lista = alvos(args.ano, args.fonte, args.uf)
    except ValueError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    manifesto = Manifesto(args.raiz / "manifesto.json")
    falhas = 0
    with httpx.Client(timeout=httpx.Timeout(30.0, read=120.0)) as cliente:
        baixador = Baixador(args.raiz, manifesto, cliente)
        for alvo in lista:
            if args.verificar:
                estado = baixador.verificar(alvo)
                falhas += estado != "ok"
                print(f"{estado:10} {alvo.destino}")
                continue
            try:
                res = baixador.baixar(alvo, forcar=args.forcar)
            except DownloadError as e:
                falhas += 1
                print(f"FALHA {alvo.destino}: {e}", file=sys.stderr)
            else:
                print(f"{res.value:10} {alvo.destino}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
