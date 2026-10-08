"""Smoke test contra uma API viva com dados reais (T-B03).

Chama todos os endpoints com parâmetros reais (Missão 2026 SP dep. federal; MBL 2022→2026;
Kim Kataguiri), valida formato e os números âncora (Kim: 295.460 votos em 2022, 520.071 em 2026)
e mede latência (1ª chamada = "frio"; demais = "quente", por cache LRU/HTTP do servidor).

Uso:
    ELEICOES_DIR_DADOS=<data/processed> uv run uvicorn api.main:app_producao --factory --port 8000
    uv run python apps/api/scripts/smoke.py [--base http://localhost:8000] [--repeticoes 20]

Sai com código 1 se qualquer verificação falhar ou p95 quente ≥ 500 ms / frio ≥ 2 s.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

# A Cloudflare bloqueia o `Python-urllib` padrão (403/1010): identificar-se explicitamente.
USER_AGENT = "eleicoes2026-smoke/1.0"
KIM_2022, KIM_2026 = 295_460, 520_071
LIMITE_FRIO_S, LIMITE_QUENTE_S = 2.0, 0.5
DF = "DEPUTADO FEDERAL"
Json = dict[str, Any]


class FalhaError(Exception):
    """Verificação do smoke que não passou."""


def _get(base: str, caminho: str, **params: object) -> tuple[int, Any, float]:
    """GET com query; devolve (status, corpo JSON, segundos)."""
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{base}{caminho}" + (f"?{qs}" if qs else "")
    ini = time.perf_counter()
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
        with urllib.request.urlopen(pedido, timeout=30) as r:  # noqa: S310 - base controlada
            return r.status, json.loads(r.read()), time.perf_counter() - ini
    except urllib.error.HTTPError as erro:
        bruto = erro.read().decode(errors="replace")
        try:
            corpo = json.loads(bruto)
        except json.JSONDecodeError:
            corpo = bruto[:200]  # 500 do servidor vem como texto
        return erro.code, corpo, time.perf_counter() - ini


def _exigir(condicao: bool, msg: str) -> None:
    if not condicao:
        raise FalhaError(msg)


def _ok(base: str, caminho: str, **params: object) -> Json:
    status, corpo, _ = _get(base, caminho, **params)
    _exigir(status == 200, f"{caminho} {params} → HTTP {status}: {str(corpo)[:200]}")
    _exigir(isinstance(corpo, dict), f"{caminho}: corpo não é objeto")
    return corpo  # type: ignore[no-any-return]


def _kim(base: str, ano: int, grupo: str) -> Json:
    itens = _ok(base, "/api/candidatos", ano=ano, uf="SP", cargo=DF, grupo=grupo, limite=500)
    achados = [i for i in itens["itens"] if i["nm_urna"] == "KIM KATAGUIRI"]
    _exigir(len(achados) == 1, f"Kim {ano}: {len(achados)} candidaturas em {grupo}")
    return achados[0]  # type: ignore[no-any-return]


def verificar(base: str) -> dict[str, Callable[[], None]]:
    """Verificações nomeadas; cada uma levanta `FalhaError`."""
    sq: dict[int, int] = {}
    sp = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "missao_2026"}

    def saude() -> None:
        c = _ok(base, "/api/health")
        _exigir(c["status"] == "ok" and bool(c["dt_geracao"]), f"health: {c}")

    def meta() -> None:
        c = _ok(base, "/api/meta")
        _exigir({2022, 2026} <= set(c["anos"]) and "SP" in c["ufs"], f"meta: {c['anos']}")

    def grupos() -> None:
        ids = {g["id"] for g in _ok(base, "/api/grupos")["grupos"]}
        _exigir({"missao_2026", "mbl_2022", "mbl_2026"} <= ids, f"grupos: {ids}")

    def kim_2022() -> None:
        kim = _kim(base, 2022, "mbl_2022")
        sq[2022] = int(kim["sq_candidato"])
        _exigir(kim["votos"] == KIM_2022, f"Kim 2022 = {kim['votos']} (esperado {KIM_2022})")

    def kim_2026() -> None:
        kim = _kim(base, 2026, "missao_2026")
        sq[2026] = int(kim["sq_candidato"])
        _exigir(kim["votos"] == KIM_2026, f"Kim 2026 = {kim['votos']} (esperado {KIM_2026})")

    def ficha() -> None:
        for ano in (2022, 2026):
            c = _ok(base, f"/api/candidatos/{ano}/{sq[ano]}")
            _exigir("gastos" in c and "receitas" in c, f"ficha {ano}: {sorted(c)}")
            _exigir("cpf" not in json.dumps(c).lower(), f"ficha {ano} vaza CPF")

    def mapa_missao() -> None:
        c = _ok(base, "/api/mapa", **sp)
        valores = c["valores"]
        _exigir(len(valores) > 600, f"SP deve ter ~645 municípios (veio {len(valores)})")
        _exigir(any(v for v in valores.values()), "mapa: nenhum valor positivo")
        _exigir(c["unidade"] == "‰", "mapa: unidade")

    def mapa_comum() -> None:
        base22 = {"ano": 2022, "cargo": DF, "uf": "SP", "grupo": "mbl_2022"}
        base26 = {"ano": 2026, "cargo": DF, "uf": "SP", "grupo": "mbl_2026"}
        a = _ok(base, "/api/mapa", comparacao="evolucao_mbl", **base22)["escala_sugerida"]
        b = _ok(base, "/api/mapa", comparacao="evolucao_mbl", **base26)["escala_sugerida"]
        _exigir(a == b, f"quebras comuns diferem: {a} × {b}")
        _exigir(bool(a["quebras"]) and a["anos"] == [2022, 2026], f"escala: {a}")

    def mapa_zona_e_h3() -> None:
        z = _ok(base, "/api/mapa", nivel="zona", **sp)
        _exigir(any("-" in k for k in z["valores"]), "zona: chaves município-zona")
        status, _, _ = _get(base, "/api/mapa", nivel="h3", **sp)
        _exigir(status in (200, 503), f"h3: HTTP {status}")  # 503 = locais_h3 ainda não gerado

    def pontos() -> None:
        status, c, _ = _get(base, "/api/mapa/pontos", **sp)
        _exigir(status in (200, 503), f"pontos: HTTP {status}")  # 503 = locais_h3 ausente
        if status == 200:
            _exigir(c["total"] > 0, "pontos: total")

    def gastos() -> None:
        c = _ok(base, "/api/gastos", **sp)
        _exigir("base_ipca" in json.dumps(c), f"gastos sem base_ipca: {sorted(c)}")

    def comparativo() -> None:
        c = _ok(base, "/api/comparativo", comparacao="evolucao_mbl", cargo=DF, uf="SP")
        k = c["kpis"]
        _exigir(k["votos_de"] >= KIM_2022 and k["votos_para"] >= KIM_2026, f"kpis: {k}")
        _exigir(bool(c["municipios"]) and bool(c["escala_sugerida"]["quebras"]), "vazio")

    def comparativo_brasil() -> None:
        c = _ok(base, "/api/comparativo", comparacao="evolucao_mbl", cargo=DF)
        _exigir(len(c["municipios"]) > 1000, f"Brasil: {len(c['municipios'])} AMCs")

    def municipio() -> None:
        c = _ok(base, "/api/municipios/3550308")
        _exigir("São Paulo" in json.dumps(c, ensure_ascii=False), "3550308 ≠ São Paulo")

    return {
        "health": saude, "meta": meta, "grupos": grupos, "kim 2022 = 295.460": kim_2022,
        "kim 2026 = 520.071": kim_2026, "ficha 2022 e 2026": ficha, "mapa missão SP": mapa_missao,
        "mapa quebras comuns": mapa_comum, "mapa zona/h3": mapa_zona_e_h3, "pontos": pontos,
        "gastos": gastos, "comparativo SP": comparativo, "comparativo BR": comparativo_brasil,
        "município SP": municipio,
    }  # fmt: skip


def latencias(base: str, repeticoes: int) -> list[tuple[str, float, float, float, bool]]:
    """(nome, frio, p50 quente, p95 quente, dentro da meta) por endpoint principal."""
    sp = {"cargo": DF, "uf": "SP", "grupo": "missao_2026"}
    comum = {"cargo": DF, "uf": "SP", "comparacao": "evolucao_mbl"}
    alvos: dict[str, tuple[str, Json]] = {
        "mapa SP município": ("/api/mapa", {"ano": 2026, **sp}),
        "mapa SP zona": ("/api/mapa", {"ano": 2026, "nivel": "zona", **sp}),
        "mapa Brasil": ("/api/mapa", {"ano": 2026, "cargo": DF, "grupo": "missao_2026"}),
        "mapa SP quebras comuns": ("/api/mapa", {**comum, "ano": 2022, "grupo": "mbl_2022"}),
        "comparativo SP": ("/api/comparativo", comum),
        "comparativo Brasil": ("/api/comparativo", {"cargo": DF, "comparacao": "evolucao_mbl"}),
        "candidatos SP": ("/api/candidatos", {"ano": 2026, **sp}),
        "gastos SP": ("/api/gastos", {"ano": 2026, **sp}),
    }
    saida = []
    for nome, (caminho, params) in alvos.items():
        status, _, frio = _get(base, caminho, **params)
        quentes = sorted(_get(base, caminho, **params)[2] for _ in range(repeticoes))
        p95 = quentes[min(len(quentes) - 1, int(0.95 * len(quentes)))]
        ok = status == 200 and frio < LIMITE_FRIO_S and p95 < LIMITE_QUENTE_S
        saida.append((f"{nome} [{status}]", frio, statistics.median(quentes), p95, ok))
    return saida


def main() -> int:
    """Roda verificações e latências; imprime tabela; código de saída 0 = tudo certo."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--repeticoes", type=int, default=20)
    args = ap.parse_args()
    falhas = 0
    medidas = latencias(args.base, args.repeticoes)  # antes de tudo: a 1ª chamada é a fria
    for nome, fn in verificar(args.base).items():
        try:
            fn()
            print(f"ok    {nome}")
        except (FalhaError, KeyError, TypeError) as erro:
            falhas += 1
            print(f"FALHA {nome}: {erro!r}")
    print(f"\n{'endpoint':30} {'frio':>8} {'p50':>8} {'p95':>8}  meta")
    for nome, frio, p50, p95, ok in medidas:
        marca = "ok" if ok else "FORA"
        print(f"{nome:30} {frio * 1000:6.0f}ms {p50 * 1000:6.0f}ms {p95 * 1000:6.0f}ms  {marca}")
        falhas += 0 if ok else 1
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
