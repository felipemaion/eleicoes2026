"""Varredura de robustez (T-B07): nenhum endpoint pode responder 5xx, para nenhuma combinação.

Percorre todos os endpoints para cargos × anos × grupos × (com/sem UF), e para candidatos do
grupo (todos os majoritários + amostra ≥ 30 dos demais). 2xx e 4xx (parâmetro incoerente: 404/422)
são respostas legítimas; o que a varredura caça é 5xx, corpo que não é JSON e demora.

Uso (contra a API viva; identifica-se por User-Agent porque a Cloudflare barra o padrão):
    uv run python apps/api/scripts/varredura.py --base https://eleicoes2026.maionesys.com
    uv run python apps/api/scripts/varredura.py --base http://localhost:8000 --ufs SP,RJ,AC,DF

O módulo também é usado por `tests/test_varredura.py` com a fixture (via `executar`).
Sai com código 1 se houver qualquer 5xx.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

USER_AGENT = "eleicoes2026-varredura/1.0"
MAJORITARIOS = ("PRESIDENTE", "GOVERNADOR", "SENADOR")
CARGOS = (
    "PRESIDENTE", "GOVERNADOR", "SENADOR",
    "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL",
)  # fmt: skip
ANOS = (2022, 2026)
NIVEIS = ("municipio", "zona", "h3")
UFS_PADRAO = ("SP", "RJ", "AC", "DF")
AMOSTRA_MINIMA = 30
BUSCAS = ("a", "silva", "14", "missao", "renan", "ç")
LENTO_S = 5.0

Json = Any
Get = Callable[[str, dict[str, object]], tuple[int, Json, float]]
Pedido = tuple[str, dict[str, object]]


@dataclass
class Relatorio:
    """Resultado da varredura."""

    total: int = 0
    por_status: dict[int, int] = field(default_factory=dict)
    cinco_xx: list[tuple[Pedido, int]] = field(default_factory=list)
    lentos: list[tuple[Pedido, float]] = field(default_factory=list)
    nao_json: list[Pedido] = field(default_factory=list)
    descoberta: list[tuple[Pedido, int]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Sem 5xx, sem corpo inválido e sem falha ao descobrir candidatos/grupos."""
        return not self.cinco_xx and not self.nao_json and not self.descoberta


def _amostra(itens: list[Json], n: int) -> list[Json]:
    """Até `n` itens espaçados (já ordenados por votos): topo e cauda, determinístico."""
    if len(itens) <= n:
        return itens
    passo = len(itens) / n
    return [itens[int(i * passo)] for i in range(n)]


def _descobrir(
    get: Get, caminho: str, params: dict[str, object], falhas: list[tuple[Pedido, int]]
) -> Json | None:
    """GET de descoberta; resposta não-200 ou sem JSON vira falha registrada, não exceção."""
    status, corpo, _ = get(caminho, params)
    if status != 200 or not isinstance(corpo, dict):
        falhas.append(((caminho, params), status))
        return None
    return corpo


def pedidos(
    get: Get,
    ufs: tuple[str, ...] = UFS_PADRAO,
    falhas: list[tuple[Pedido, int]] | None = None,
) -> Iterator[Pedido]:
    """Gera os pedidos da varredura, descobrindo grupos e candidatos pela própria API.

    Descoberta que falha entra em `falhas` e a parte dependente dela é pulada.
    """
    falhas = falhas if falhas is not None else []
    corpo = _descobrir(get, "/api/grupos", {}, falhas)
    if corpo is None:
        return
    grupos = corpo["grupos"]
    comparacoes = corpo["comparacoes"]
    recortes: list[str | None] = [None, *ufs]
    for ano in ANOS:
        yield "/api/candidatos/ufs", {"ano": ano}
        for cargo in CARGOS:
            yield "/api/candidatos/ufs", {"ano": ano, "cargo": cargo}
    for g in grupos:
        yield "/api/candidatos/ufs", {"grupo": g["id"]}
        for cargo in CARGOS:
            yield "/api/candidatos/ufs", {"grupo": g["id"], "cargo": cargo}
            for uf in recortes:
                base = {"grupo": g["id"], "cargo": cargo, "uf": uf}
                yield "/api/candidatos", base
                yield "/api/gastos", base
                yield "/api/mapa/pontos", {**base, "ano": g["ano"]}
                for nivel in NIVEIS:
                    for ind in ("penetracao", "votos"):
                        yield (
                            "/api/mapa",
                            {**base, "ano": g["ano"], "nivel": nivel, "indicador": ind},
                        )
    for ano in ANOS:  # ano incoerente com o grupo também não pode virar 5xx
        for cargo in CARGOS:
            yield "/api/mapa", {"ano": ano, "cargo": cargo, "grupo": grupos[0]["id"]}
    for c in comparacoes:
        for cargo in CARGOS:
            for uf in recortes:
                for mesmos in (False, True):
                    yield (
                        "/api/comparativo",
                        {
                            "comparacao": c["id"],
                            "cargo": cargo,
                            "uf": uf,
                            "mesmos_candidatos": mesmos,
                        },
                    )
    yield from _por_candidato(get, grupos, ufs, falhas)
    for q in BUSCAS:
        yield "/api/busca", {"q": q}
        for g in grupos:
            yield "/api/busca", {"q": q, "grupo": g["id"]}
    yield "/api/evolucao/pessoas", {}
    for cargo in CARGOS:
        yield "/api/evolucao/pessoas", {"cargo": cargo}


def _por_candidato(
    get: Get, grupos: list[Json], ufs: tuple[str, ...], falhas: list[tuple[Pedido, int]]
) -> Iterator[Pedido]:
    """Ficha, mapa, pontos e comparativo de cada candidato escolhido (majoritários + amostra)."""
    pessoas: set[str] = set()
    for g in grupos:
        corpo = _descobrir(get, "/api/candidatos", {"grupo": g["id"], "limite": 500}, falhas)
        if corpo is None:
            continue
        itens = corpo["itens"]
        majoritarios = [i for i in itens if i["cargo"] in MAJORITARIOS]
        outros = [i for i in itens if i["cargo"] not in MAJORITARIOS]
        for i in [*majoritarios, *_amostra(outros, AMOSTRA_MINIMA)]:
            ano, sq, cargo = i["ano"], i["sq_candidato"], i["cargo"]
            yield f"/api/candidatos/{ano}/{sq}", {}
            for uf in (None, i["sg_uf"] if i["sg_uf"] != "BR" else ufs[0]):
                alvo = {"ano": ano, "cargo": cargo, "uf": uf, "sq_candidato": sq}
                yield "/api/mapa", alvo
                yield "/api/mapa/pontos", alvo
            yield "/api/busca", {"q": i["nm_urna"], "ano": ano}
        busca = _descobrir(get, "/api/busca", {"q": "a", "grupo": g["id"], "limite": 100}, falhas)
        if busca is not None:
            pessoas |= {i["pessoa_id_publico"] for i in busca["itens"]}
    for p in sorted(pessoas)[:AMOSTRA_MINIMA]:
        for cargo in CARGOS:
            yield "/api/comparativo", {"cargo": cargo, "pessoas": p}


def executar(get: Get, ufs: tuple[str, ...] = UFS_PADRAO, maximo: int | None = None) -> Relatorio:
    """Roda os pedidos e junta o que não pode acontecer: 5xx, corpo não-JSON, lentidão."""
    rel = Relatorio()
    for n, (caminho, params) in enumerate(pedidos(get, ufs, rel.descoberta)):
        if maximo is not None and n >= maximo:
            break
        pedido = (caminho, {k: v for k, v in params.items() if v is not None})
        status, corpo, segundos = get(*pedido)
        rel.total += 1
        rel.por_status[status] = rel.por_status.get(status, 0) + 1
        if status >= 500:
            rel.cinco_xx.append((pedido, status))
        elif corpo is None:
            rel.nao_json.append(pedido)
        if segundos > LENTO_S:
            rel.lentos.append((pedido, segundos))
    return rel


def get_http(base: str) -> Get:
    """`Get` real sobre urllib, com User-Agent explícito."""

    def get(caminho: str, params: dict[str, object]) -> tuple[int, Json, float]:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        url = f"{base}{caminho}" + (f"?{qs}" if qs else "")
        ini = time.perf_counter()
        pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:  # noqa: S310 - base controlada
                return r.status, json.loads(r.read()), time.perf_counter() - ini
        except urllib.error.HTTPError as erro:
            bruto = erro.read().decode(errors="replace")
            try:
                corpo = json.loads(bruto)
            except json.JSONDecodeError:
                corpo = None
            return erro.code, corpo, time.perf_counter() - ini
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return 0, None, time.perf_counter() - ini  # sem resposta utilizável: status 0

    return get


def main() -> int:
    """CLI: imprime o resumo e os 5xx; código 1 se houver falha."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--ufs", default=",".join(UFS_PADRAO), help="UFs da varredura (vírgula)")
    ap.add_argument("--maximo", type=int, default=None, help="limita o nº de pedidos")
    args = ap.parse_args()
    rel = executar(get_http(args.base.rstrip("/")), tuple(args.ufs.split(",")), args.maximo)
    print(f"{rel.total} pedidos; status: {dict(sorted(rel.por_status.items()))}")
    for (caminho, params), status in rel.cinco_xx:
        print(f"5xx {status}: {caminho} {params}")
    for (caminho, params), status in rel.descoberta:
        print(f"descoberta falhou ({status}): {caminho} {params}")
    for caminho, params in rel.nao_json:
        print(f"sem JSON: {caminho} {params}")
    for (caminho, params), s in rel.lentos:
        print(f"lento {s:.1f}s: {caminho} {params}")
    return 0 if rel.ok else 1


if __name__ == "__main__":
    sys.exit(main())
