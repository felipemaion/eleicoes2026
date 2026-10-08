"""T-B18: correlações com n ≥ 10 e perfil compartilhado por duas candidaturas.

A fixture padrão tem poucos candidatos. Aqui o mundo ganha 14 candidaturas do Missão (dep. federal
SP) escritas ao lado dos Parquet existentes: as expectativas vêm do `scipy` (ρ e reta log-log),
independente de `indicadores`, e o `username` compartilhado (sq 112 e 113) prova que cada
candidatura mantém os próprios posts.
"""

import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient
from scipy import stats

FIXTURES = Path(__file__).parent / "fixtures"
COLETA = datetime(2026, 10, 8, 12, tzinfo=UTC)
DT = datetime(2026, 10, 6).date()
# (sq, votos, seguidores, username): votos e seguidores sem relação monótona perfeita
EXTRAS = [
    (100, 120, 900, "x100"), (101, 80, 500, "x101"), (102, 300, 4000, "x102"),
    (103, 45, 700, "x103"), (104, 220, 1500, "x104"), (105, 510, 9000, "x105"),
    (106, 90, 400, "x106"), (107, 160, 2500, "x107"), (108, 700, 8000, "x108"),
    (109, 60, 300, "x109"), (110, 410, 3200, "x110"), (111, 250, 1200, "x111"),
    (112, 55, 600, "dupla"), (113, 65, 600, "dupla"),
]  # fmt: skip
DF = "DEPUTADO FEDERAL"


def _estender(destino: Path) -> None:
    """Acrescenta as candidaturas extras (cadastro, votos, redes) à cópia da fixture."""
    con = duckdb.connect()
    ids = ", ".join(f"({sq}, {v}, '{u}')" for sq, v, _, u in EXTRAS)
    con.execute(
        f"CREATE TABLE novos(sq BIGINT, votos BIGINT, u VARCHAR); INSERT INTO novos VALUES {ids}"
    )
    base = FIXTURES / "consulta_cand" / "ano=2026" / "consulta_cand.parquet"
    con.execute(
        f"COPY (SELECT c.* REPLACE (n.sq AS sq_candidato, 'E' || n.sq AS nm_urna_candidato, "
        "'pe' || n.sq AS pessoa_id, n.sq AS nr_candidato) "
        f"FROM read_parquet('{base}') c, novos n WHERE c.sq_candidato = 5) "
        f"TO '{destino / 'consulta_cand' / 'ano=2026' / 'extras.parquet'}' (FORMAT PARQUET)"
    )
    votos = (
        FIXTURES / "votacao_candidato_munzona" / "ano=2026" / "votacao_candidato_munzona.parquet"
    )
    con.execute(
        f"COPY (SELECT v.* REPLACE (n.sq AS sq_candidato, n.votos AS qt_votos_nominais_validos, "
        "n.votos AS qt_votos_nominais) "
        f"FROM read_parquet('{votos}') v, novos n WHERE v.sq_candidato = 5 AND v.cd_mun_ibge = "
        f"(SELECT min(cd_mun_ibge) FROM read_parquet('{votos}') WHERE sq_candidato = 5)) "
        f"TO '{destino / 'votacao_candidato_munzona' / 'ano=2026' / 'extras.parquet'}' "
        "(FORMAT PARQUET)"
    )
    declarados = pl.read_parquet(
        FIXTURES / "redes_candidatos" / "ano=2026" / "redes_candidatos.parquet"
    )
    novos_declarados = pl.DataFrame(
        {
            "ano_eleicao": [2026] * len(EXTRAS),
            "sq_candidato": [e[0] for e in EXTRAS],
            "rede": ["instagram"] * len(EXTRAS),
            "username": [e[3] for e in EXTRAS],
            "url_tse": [f"https://instagram.com/{e[3]}" for e in EXTRAS],
            "nr_ordem": [1] * len(EXTRAS),
            "principal": [True] * len(EXTRAS),
            "dt_geracao": [DT] * len(EXTRAS),
        },
        schema=declarados.schema,
    )
    pl.concat([declarados, novos_declarados]).write_parquet(
        destino / "redes_candidatos" / "ano=2026" / "redes_candidatos.parquet"
    )
    perfis = pl.read_parquet(FIXTURES / "redes" / "redes_perfis.parquet")
    novos_perfis = pl.DataFrame(
        {
            "sq_candidato": [e[0] for e in EXTRAS],
            "ano_eleicao": [2026] * len(EXTRAS),
            "rede": ["instagram"] * len(EXTRAS),
            "username": [e[3] for e in EXTRAS],
            "status": ["ok"] * len(EXTRAS),
            "followers_count": [e[2] for e in EXTRAS],
            "follows_count": [10] * len(EXTRAS),
            "media_count": [5] * len(EXTRAS),
            "coletado_em": [COLETA] * len(EXTRAS),
        },
        schema=perfis.schema,
    )
    pl.concat([perfis, novos_perfis]).write_parquet(destino / "redes" / "redes_perfis.parquet")
    posts = pl.read_parquet(FIXTURES / "redes" / "redes_posts.parquet")
    um_post = pl.DataFrame(
        {
            "username": ["dupla"],
            "media_id": ["dp1"],
            "timestamp": [datetime(2026, 9, 1, 15, tzinfo=UTC)],
            "media_type": ["IMAGE"],
            "media_product_type": ["FEED"],
            "like_count": [60],
            "comments_count": [6],
            "permalink": ["https://instagram.com/p/dp1"],
            "coletado_em": [COLETA],
        },
        schema=posts.schema,
    )
    pl.concat([posts, um_post]).write_parquet(destino / "redes" / "redes_posts.parquet")


@pytest.fixture(scope="module")
def api_grande(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """App sobre a fixture ampliada (14 candidaturas a mais no Missão, dep. federal SP)."""
    destino = tmp_path_factory.mktemp("mundo_grande")
    shutil.copytree(FIXTURES, destino, dirs_exist_ok=True)
    _estender(destino)
    cfg = Settings(
        dir_dados=destino,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        versao_app="teste",
        aquecer=False,
    )
    with TestClient(criar_app(cfg)) as cliente:
        yield cliente


PARAMS = {"grupo": "missao_2026", "uf": "SP", "cargo": DF}


def _pares_esperados() -> tuple[list[int], list[int]]:
    """(seguidores, votos) de quem tem números: sq 3 (10500, 1000) e as extras."""
    dados = [(10500, 1000), *[(e[2], e[1]) for e in EXTRAS]]
    return [d[0] for d in dados], [d[1] for d in dados]


def test_rho_de_spearman_confere_com_scipy(api_grande: TestClient) -> None:
    (recorte,) = api_grande.get("/api/redes/correlacoes", params=PARAMS).json()["recortes"]
    seg, votos = _pares_esperados()
    par = {p["id"]: p for p in recorte["pares"]}["seguidores_votos"]
    assert par["n"] == 15
    assert par["n_excluidos"] == 1  # sq 5: perfil indisponível
    assert par["rho"] == pytest.approx(stats.spearmanr(seg, votos).statistic, abs=1e-9)
    assert par["ic_inf"] < par["rho"] < par["ic_sup"]
    assert par["n_bootstrap_validos"] > 1900


def test_engajamento_e_ritmo_com_poucos_pares_ficam_nulos(api_grande: TestClient) -> None:
    (recorte,) = api_grande.get("/api/redes/correlacoes", params=PARAMS).json()["recortes"]
    pares = {p["id"]: p for p in recorte["pares"]}
    # só ana_alves (sq 3), dupla e as demais têm posts: engajamento exige ≥ 10 pares
    assert pares["engajamento_votos"]["rho"] is None
    assert pares["engajamento_votos"]["n"] < 10


def test_ajuste_log_log_confere_com_scipy(api_grande: TestClient) -> None:
    (recorte,) = api_grande.get("/api/redes/correlacoes", params=PARAMS).json()["recortes"]
    seg, votos = _pares_esperados()
    reta = stats.linregress(np.log10(1 + np.array(seg)), np.log10(1 + np.array(votos)))
    assert recorte["ajuste"]["inclinacao"] == pytest.approx(reta.slope, abs=1e-9)
    assert recorte["ajuste"]["intercepto"] == pytest.approx(reta.intercept, abs=1e-9)
    assert recorte["ajuste"]["n"] == 15
    esperado = 10 ** (reta.intercept + reta.slope * np.log10(1 + 10500)) - 1
    ponto = {p["sq_candidato"]: p for p in recorte["pontos"]}[3]
    assert ponto["razao_obs_esperado"] == pytest.approx((1 + 1000) / (1 + esperado), rel=1e-9)


def test_voto_esperado_na_lista_de_candidatos(api_grande: TestClient) -> None:
    corpo = api_grande.get("/api/redes", params=PARAMS).json()
    c3 = {c["sq_candidato"]: c for c in corpo["candidatos"]}[3]
    assert c3["voto_esperado"]["razao_obs_esperado"] > 0
    assert corpo["agregado"]["n_com_dados"] == 15


def test_perfil_compartilhado_mantem_os_posts_de_cada_candidatura(api_grande: TestClient) -> None:
    corpo = api_grande.get("/api/redes", params=PARAMS).json()
    por_sq = {c["sq_candidato"]: c for c in corpo["candidatos"]}
    for sq in (112, 113):
        total = {j["janela"]: j for j in por_sq[sq]["janelas"]}["total"]
        assert total["n_posts"] == 1
        assert por_sq[sq]["perfis"][0]["username"] == "dupla"


def test_serie_por_username_compartilhado_conta_uma_vez(api_grande: TestClient) -> None:
    (serie,) = api_grande.get("/api/redes/serie", params={"username": "dupla"}).json()["series"]
    assert len(serie["pontos"]) == 1  # duas candidaturas, uma única coleta do perfil


def test_pontos_ordenados_por_votos(api_grande: TestClient) -> None:
    (recorte,) = api_grande.get("/api/redes/correlacoes", params=PARAMS).json()["recortes"]
    votos = [p["votos"] for p in recorte["pontos"]]
    assert votos == sorted(votos, reverse=True)
