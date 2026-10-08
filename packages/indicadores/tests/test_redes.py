"""Indicadores de redes sociais (spec §9): conferência com scipy e casos de borda.

Os vetores da spec (test_vetores_impl.py) fixam os números; aqui o ρ, o IC bootstrap e o ajuste
log-log são comparados com implementações independentes do scipy.
"""

import math
import random
from datetime import datetime

import numpy as np
import polars as pl
import pytest
from indicadores import redes
from scipy import stats  # type: ignore[import-untyped]


def _amostra(n: int, semente: int) -> tuple[list[int], list[int]]:
    """Seguidores e votos com cauda longa, correlação moderada e empates."""
    rng = random.Random(semente)  # noqa: S311 - dados sintéticos de teste
    seguidores = [int(10 ** rng.uniform(2, 6)) // 100 * 100 for _ in range(n)]
    votos = [max(0, int(s**0.6 * 10 ** rng.gauss(1, 0.4))) for s in seguidores]
    return seguidores, votos


def _linhas(seguidores: list[int], votos: list[int], cargo: int = 6) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sq_candidato": list(range(len(seguidores))),
            "cd_cargo": [cargo] * len(seguidores),
            "seguidores": seguidores,
            "votos": votos,
        }
    )


@pytest.mark.parametrize("semente", [1, 2, 3])
def test_rho_igual_ao_scipy(semente: int) -> None:
    seguidores, votos = _amostra(40, semente)
    obtido = redes.correlacao(_linhas(seguidores, votos), "seguidores", "votos", n_bootstrap=10)
    esperado = stats.spearmanr(seguidores, votos).statistic
    assert obtido["rho"][0] == pytest.approx(esperado, abs=1e-12)


def test_log_nao_muda_o_rho() -> None:
    seguidores, votos = _amostra(30, 7)
    bruto = redes.correlacao(_linhas(seguidores, votos), "seguidores", "votos", n_bootstrap=10)
    logs = _linhas(seguidores, votos).with_columns(
        pl.col("seguidores").log1p(), pl.col("votos").log1p()
    )
    log = redes.correlacao(logs, "seguidores", "votos", n_bootstrap=10)
    assert bruto["rho"][0] == pytest.approx(log["rho"][0], abs=1e-12)


def test_ic_bootstrap_proximo_do_scipy() -> None:
    """Geradores diferentes → ICs diferentes por ruído de Monte Carlo; com B grande, ~0,03."""
    seguidores, votos = _amostra(60, 11)
    obtido = redes.correlacao(
        _linhas(seguidores, votos), "seguidores", "votos", n_bootstrap=4000
    ).row(0, named=True)

    def rho(x: np.ndarray, y: np.ndarray) -> float:
        return float(stats.spearmanr(x, y).statistic)

    ref = stats.bootstrap(
        (np.array(seguidores), np.array(votos)),
        rho,
        paired=True,
        vectorized=False,
        n_resamples=4000,
        method="percentile",
        confidence_level=0.95,
        rng=np.random.default_rng(2026),
    ).confidence_interval
    assert obtido["ic_inf"] == pytest.approx(ref.low, abs=0.03)
    assert obtido["ic_sup"] == pytest.approx(ref.high, abs=0.03)
    assert obtido["ic_inf"] < obtido["rho"] < obtido["ic_sup"]
    assert obtido["n_bootstrap_validos"] == 4000


def test_bootstrap_reprodutivel_e_sensivel_a_semente() -> None:
    df = _linhas(*_amostra(25, 5))
    a = redes.correlacao(df, "seguidores", "votos", n_bootstrap=200, semente=1)
    b = redes.correlacao(df.reverse(), "seguidores", "votos", n_bootstrap=200, semente=1)
    c = redes.correlacao(df, "seguidores", "votos", n_bootstrap=200, semente=2)
    assert a["ic_inf"][0] == b["ic_inf"][0]  # ordem de entrada não importa
    assert a["ic_inf"][0] != c["ic_inf"][0]


def test_correlacao_por_cargo_e_uf() -> None:
    s1, v1 = _amostra(12, 1)
    s2, v2 = _amostra(15, 2)
    df = pl.concat([_linhas(s1, v1), _linhas(s2, v2)]).with_columns(
        pl.Series("sg_uf", ["SP"] * 12 + ["RJ"] * 15)
    )
    out = redes.correlacao(df, "seguidores", "votos", por=("cd_cargo", "sg_uf"), n_bootstrap=10)
    assert out.select("sg_uf", "n").to_dicts() == [
        {"sg_uf": "RJ", "n": 15},
        {"sg_uf": "SP", "n": 12},
    ]
    assert out.filter(sg_uf="SP")["rho"][0] == pytest.approx(stats.spearmanr(s1, v1).statistic)


def test_correlacao_sem_variancia_e_coluna_ausente() -> None:
    df = _linhas([5] * 12, list(range(12)))
    assert redes.correlacao(df, "seguidores", "votos", n_bootstrap=10)["rho"][0] is None
    with pytest.raises(ValueError, match="colunas ausentes"):
        redes.correlacao(df, "engajamento", "votos")
    with pytest.raises(ValueError, match="nivel"):
        redes.correlacao(df, "seguidores", "votos", nivel=1.2)


def test_residuo_igual_ao_linregress() -> None:
    seguidores, votos = _amostra(30, 9)
    out = redes.residuo_log(_linhas(seguidores, votos))
    lx = np.log10(1 + np.array(seguidores, dtype=float))
    ly = np.log10(1 + np.array(votos, dtype=float))
    ref = stats.linregress(lx, ly)
    assert out["inclinacao"][0] == pytest.approx(ref.slope, abs=1e-10)
    assert out["intercepto"][0] == pytest.approx(ref.intercept, abs=1e-10)
    residuos = ly - (ref.intercept + ref.slope * lx)
    assert out["residuo_log10"].to_list() == pytest.approx(list(residuos), abs=1e-10)
    # Resíduos de MQO somam zero; a razão é 10^resíduo.
    assert math.fsum(out["residuo_log10"].to_list()) == pytest.approx(0, abs=1e-9)
    assert out["razao_obs_esperado"][0] == pytest.approx(10 ** residuos[0])


def _perfil(username: str, seguidores: int | None, coletado: datetime) -> dict[str, object]:
    return {
        "sq_candidato": 1,
        "username": username,
        "status": "ok" if seguidores is not None else "nao_comercial",
        "followers_count": seguidores,
        "follows_count": None,
        "media_count": None,
        "coletado_em": coletado,
    }


def test_datas_sem_fuso_sao_tratadas_como_utc() -> None:
    """Parquet sem fuso (contrato diz UTC) dá o mesmo resultado que o com fuso."""
    coleta = datetime(2026, 10, 20, 12)
    perfis = pl.DataFrame([_perfil("ana", 100, coleta)])
    posts = pl.DataFrame(
        {
            "username": ["ana"],
            "media_id": ["1"],
            "timestamp": [datetime(2026, 10, 5, 2, 30)],  # 04/10 23h30 em Brasília
            "media_type": ["VIDEO"],
            "media_product_type": ["REELS"],
            "like_count": [10],
            "comments_count": [0],
            "coletado_em": [coleta],
        }
    )
    ingenuo = redes.metricas_janelas(perfis, posts)
    utc = redes.metricas_janelas(
        perfis.with_columns(pl.col("coletado_em").dt.replace_time_zone("UTC")),
        posts.with_columns(pl.col("timestamp", "coletado_em").dt.replace_time_zone("UTC")),
    )
    assert ingenuo.equals(utc)
    assert ingenuo.filter(janela="campanha")["n_posts"][0] == 1


def test_posts_de_conta_sem_perfil_sao_ignorados_e_colunas_exigidas() -> None:
    coleta = datetime(2026, 10, 20, 12)
    perfis = pl.DataFrame([_perfil("ana", 100, coleta)])
    posts = pl.DataFrame(
        {
            "username": ["outra"],
            "media_id": ["1"],
            "timestamp": [datetime(2026, 9, 1)],
            "media_type": ["IMAGE"],
            "media_product_type": ["FEED"],
            "like_count": [1],
            "comments_count": [1],
            "coletado_em": [coleta],
        }
    )
    out = redes.metricas_janelas(perfis, posts)
    assert out["username"].unique().to_list() == ["ana"]
    assert out["n_posts"].sum() == 0
    with pytest.raises(ValueError, match="colunas ausentes"):
        redes.metricas_janelas(perfis, posts.drop("like_count"))


def test_erros_falham_alto() -> None:
    df = _linhas(*_amostra(12, 4))
    with pytest.raises(ValueError, match="n_bootstrap"):
        redes.correlacao(df, "seguidores", "votos", n_bootstrap=0)
    with pytest.raises(ValueError, match="negativos"):
        redes.residuo_log(df.with_columns(pl.lit(-1).alias("votos")))
    perfis = pl.DataFrame([_perfil("ana", 1, datetime(2026, 10, 8))]).with_columns(
        pl.col("coletado_em").cast(pl.String)
    )
    with pytest.raises(ValueError, match="data/hora"):
        redes.ultimo_snapshot(perfis)
    with pytest.raises(ValueError, match="tamanhos diferentes"):
        redes.spearman_listas([1.0, 2.0], [1.0])
