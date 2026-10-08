"""CLI: ``etl baixar --ano 2026 [--fonte ID ...] [--uf SP]``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from etl.download import Baixador, DownloadError
from etl.fontes.catalogo import CATALOGO, alvos
from etl.manifesto import Manifesto


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="etl")
    sub = p.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("baixar", help="baixa fontes oficiais para data/raw")
    b.add_argument("--ano", type=int, required=True)
    b.add_argument("--fonte", action="append", choices=sorted(CATALOGO), help="repetível")
    b.add_argument("--uf", help="restringe fontes por UF (ex.: SP)")
    b.add_argument("--raiz", type=Path, default=Path("data/raw"))
    b.add_argument("--forcar", action="store_true", help="ignora o cache")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada; devolve o código de saída."""
    args = _parser().parse_args(argv)
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
