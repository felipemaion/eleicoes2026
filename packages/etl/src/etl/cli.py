"""CLI: ``etl baixar --ano 2026 [--fonte ID ...] [--uf SP]``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import polars as pl
from contratos import ContratoViolado

from etl.download import Baixador, DownloadError
from etl.fontes.catalogo import CATALOGO, alvos
from etl.fotos import ErroFotos, processar_fotos, selecionar_sqs
from etl.geo import ErroGeo
from etl.ipca import processar_ipca
from etl.manifesto import Manifesto
from etl.municipios import ErroMunicipios
from etl.pipeline_geo import construir_geo
from etl.processar import CONTAS, FONTES, ErroProcessamento, processar_fonte
from etl.redes.coleta import coletar
from etl.redes.divergencias import baixar_site, comparar, extrair_do_site
from etl.redes.execucao import carregar_env, conferir_token
from etl.redes.meta import ClienteMeta, ErroLimite, ErroMeta
from etl.redes.tse import ErroRedes, processar_redes_tse
from etl.secao import ALERTA_SEM_COORDENADA, processar_secao


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
    g = sub.add_parser("geo", help="municipios.parquet + PMTiles (municípios, UFs, zonas)")
    g.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    g.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    g.add_argument("--saida", type=Path, default=Path("data/processed/tiles"))
    s = sub.add_parser("secao", help="votacao_secao → votos_local, totais_local e locais_h3")
    s.add_argument("--ano", type=int, required=True)
    s.add_argument("--uf", action="append", help="repetível; padrão: todas as UFs do catálogo")
    s.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    s.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    s.add_argument("--baixar", action="store_true", help="baixa cada UF antes de processá-la")
    s.add_argument(
        "--descartar-zip", action="store_true", help="apaga o ZIP de cada UF após validar"
    )
    f = sub.add_parser("fotos", help="fotos oficiais (ZIPs TSE) → WebP 160×200 + manifesto")
    f.add_argument("--ano", type=int, required=True)
    f.add_argument("--uf", action="append", help="repetível; padrão: todas as UFs com ZIP")
    f.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    f.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    f.add_argument("--baixar", action="store_true", help="baixa os ZIPs antes de processar")
    r = sub.add_parser("redes-tse", help="URLs de redes sociais do TSE → redes_candidatos")
    r.add_argument("--ano", type=int, default=2026)
    r.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    r.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    r.add_argument(
        "--repo", type=Path, default=Path("."), help="raiz com config/ e data/reference/"
    )
    r.add_argument("--baixar", action="store_true", help="baixa o ZIP do TSE antes de processar")
    k = sub.add_parser("redes-coletar", help="snapshot do Instagram (Business Discovery)")
    k.add_argument("--ano", type=int, default=2026)
    k.add_argument("--limite", type=int, help="no máximo N usernames (medição, lotes)")
    k.add_argument("--username", action="append", help="repetível; restringe a estes perfis")
    k.add_argument("--env", type=Path, default=Path(".env"))
    k.add_argument("--hoje", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    k.add_argument("--raiz-raw", type=Path, default=Path("data/raw"))
    k.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    d = sub.add_parser("redes-divergencias", help="TSE × candidatos.missao.org.br (só relatório)")
    d.add_argument("--ano", type=int, default=2026)
    d.add_argument("--html", type=Path, help="HTML já baixado (padrão: baixa do site)")
    d.add_argument("--raiz-processed", type=Path, default=Path("data/processed"))
    d.add_argument(
        "--saida", type=Path, default=Path("data/reference/redes_divergencias_missao.csv")
    )
    return p


def _redes_divergencias(args: argparse.Namespace) -> int:
    base = args.raiz_processed
    redes = base / "redes_candidatos" / f"ano={args.ano}" / "redes_candidatos.parquet"
    cands = sorted((base / "consulta_cand" / f"ano={args.ano}").glob("*.parquet"))
    if not redes.exists() or not cands:
        print(
            "FALHA redes-divergencias: rode o ETL de consulta_cand e `etl redes-tse`",
            file=sys.stderr,
        )
        return 1
    try:
        html = args.html.read_text(encoding="utf-8") if args.html else baixar_site()
    except (OSError, httpx.HTTPError) as e:
        print(f"FALHA redes-divergencias: {type(e).__name__}", file=sys.stderr)
        return 1
    nomes = (
        pl.scan_parquet(cands)
        .select("sq_candidato", "nm_urna_candidato", "sg_uf")
        .unique("sq_candidato")
        .collect()
    )
    relatorio = comparar(pl.read_parquet(redes), extrair_do_site(html), nomes)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    relatorio.write_csv(args.saida)
    print(
        json.dumps(
            relatorio["divergencia"].value_counts().sort("divergencia").to_dicts(),
            ensure_ascii=False,
        )
    )
    return 0


def _redes_tse(args: argparse.Namespace) -> int:
    try:
        if args.baixar:
            manifesto = Manifesto(args.raiz_raw / "manifesto.json")
            with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as cliente:
                baixador = Baixador(args.raiz_raw, manifesto, cliente)
                for alvo in alvos(args.ano, ["rede_social_candidato"]):
                    print(f"{baixador.baixar(alvo).value}: {alvo.destino}", flush=True)
        stats = processar_redes_tse(args.ano, args.raiz_raw, args.raiz_processed, repo=args.repo)
    except (ErroRedes, ContratoViolado, DownloadError) as e:
        print(f"FALHA redes-tse: {e}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _redes_coletar(args: argparse.Namespace) -> int:
    """Códigos de saída: 0 ok · 1 falha (token, permissão, dados) · 3 limite — retomar depois."""
    env = carregar_env(args.env)
    if not env.get("META_TOKEN"):
        print("FALHA redes-coletar: META_TOKEN ausente (.env ou ambiente)", file=sys.stderr)
        return 1
    arquivo = args.raiz_processed / "redes_candidatos" / f"ano={args.ano}"
    arquivo /= "redes_candidatos.parquet"
    if not arquivo.exists():
        print(f"FALHA redes-coletar: {arquivo} não existe — rode `etl redes-tse`", file=sys.stderr)
        return 1
    candidatos = pl.read_parquet(arquivo)
    if args.username:
        candidatos = candidatos.filter(pl.col("username").is_in(args.username))
    try:
        cliente = ClienteMeta(env["META_TOKEN"])
        conferir_token(cliente, env, args.hoje or datetime.now(UTC).date())
        stats = coletar(
            cliente,
            cliente.conta_instagram(),
            candidatos,
            raiz_raw=args.raiz_raw,
            raiz_processed=args.raiz_processed,
            agora=lambda: datetime.now(UTC),
            limite=args.limite,
        )
    except ErroLimite as e:
        print(
            f"LIMITE redes-coletar: {e}. O progresso foi gravado; retome (make redes).",
            file=sys.stderr,
        )
        return 3
    except (ErroMeta, ContratoViolado) as e:
        print(f"FALHA redes-coletar: {e}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _fotos(args: argparse.Namespace) -> int:
    manifesto = Manifesto(args.raiz_raw / "manifesto.json")
    ufs = args.uf or [None]
    destinos = [a for u in ufs for a in alvos(args.ano, ["fotos"], uf=u)]
    try:
        if args.baixar:
            with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as cliente:
                baixador = Baixador(args.raiz_raw, manifesto, cliente)
                for alvo in destinos:
                    print(f"{baixador.baixar(alvo).value}: {alvo.destino}", flush=True)
        zips = [args.raiz_raw / a.destino for a in destinos]
        stats = processar_fotos(
            args.ano,
            zips,
            args.raiz_processed / "fotos",
            sqs=selecionar_sqs(args.raiz_processed, args.ano),
        )
    except (ErroFotos, DownloadError, FileNotFoundError) as e:
        print(f"FALHA fotos: {e}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _secao(args: argparse.Namespace) -> int:
    manifesto = Manifesto(args.raiz_raw / "manifesto.json")
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, read=120.0)) as cliente:
            baixador = Baixador(args.raiz_raw, manifesto, cliente)
            stats = processar_secao(
                args.ano,
                args.raiz_raw,
                args.raiz_processed,
                ufs=args.uf,
                manifesto=manifesto,
                descartar_zip=args.descartar_zip,
                baixar=baixador.baixar if args.baixar else None,
            )
    except (ErroProcessamento, ContratoViolado, DownloadError) as e:
        print(f"FALHA secao: {e}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
    if stats["pct_votos_sem_coordenada"] > ALERTA_SEM_COORDENADA:
        print(
            f"ALERTA: {stats['pct_votos_sem_coordenada']:.1%} dos votos nominais em locais sem "
            f"coordenada (limite {ALERTA_SEM_COORDENADA:.0%})",
            file=sys.stderr,
        )
    return 0


def _geo(args: argparse.Namespace) -> int:
    try:
        stats = construir_geo(args.raiz_raw, args.raiz_processed, args.saida)
    except (ErroGeo, ErroMunicipios, ContratoViolado) as e:
        print(f"FALHA geo: {e}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


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
    if args.comando == "geo":
        return _geo(args)
    if args.comando == "fotos":
        return _fotos(args)
    if args.comando == "redes-tse":
        return _redes_tse(args)
    if args.comando == "redes-divergencias":
        return _redes_divergencias(args)
    if args.comando == "redes-coletar":
        return _redes_coletar(args)
    if args.comando == "secao":
        return _secao(args)
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
