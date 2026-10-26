"""T-B23: `erro_transitorio` (perfil) e `parcial` (coleta) da T-D15 não derrubam a API.

DuckDB real sobre as fixtures Parquet; o perfil de `bruno_lima` vira `erro_transitorio`.
"""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
PARAMS = {"grupo": "missao_2026", "cargo": "DEPUTADO FEDERAL", "uf": "SP"}


def _copiar_redes(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ("redes_perfis.parquet", "redes_posts.parquet"):
        shutil.copy(FIXTURES / "redes" / nome, destino / nome)
    return destino


def _api(dir_redes: Path) -> TestClient:
    cfg = Settings(
        dir_dados=FIXTURES,
        redes_dir=dir_redes,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        versao_app="teste",
        aquecer=False,
    )
    return TestClient(criar_app(cfg))


def _com_erro_transitorio(dir_redes: Path) -> None:
    arquivo = dir_redes / "redes_perfis.parquet"
    perfis = pl.read_parquet(arquivo)
    perfis.with_columns(
        pl.when(pl.col("username") == "bruno_lima")
        .then(pl.lit("erro_transitorio"))
        .otherwise(pl.col("status"))
        .alias("status")
    ).write_parquet(arquivo)


def test_rotas_de_redes_aceitam_perfil_erro_transitorio(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    _com_erro_transitorio(dir_redes)
    with _api(dir_redes) as api:
        lista = api.get("/api/redes", params=PARAMS)
        assert lista.status_code == 200, lista.text
        status = {c["username"]: c["status"] for c in lista.json()["candidatos"] if c["username"]}
        assert status["bruno_lima"] == "erro_transitorio"
        assert lista.json()["excluidos"]["indisponivel"] >= 1
        for rota in ("/api/redes/serie", "/api/redes/correlacoes"):
            assert api.get(rota, params=PARAMS).status_code in (200, 404), rota


def test_health_coleta_parcial_avanca_ultima_ok_e_expoe_erros(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    ha_1_dia = datetime.now(UTC) - timedelta(days=1, hours=1)
    (dir_redes / "status.json").write_text(
        json.dumps(
            {
                "inicio": ha_1_dia.isoformat(),
                "fim": ha_1_dia.isoformat(),
                "resultado": "parcial",
                "motivo": "7% dos perfis com erro",
                "perfis_coletados": 100,
                "perfis_com_erro": 7,
                "coletado_em": ha_1_dia.isoformat(),
            }
        )
    )
    with _api(dir_redes) as api:
        redes = api.get("/api/health").json()["redes"]
    assert redes["resultado"] == "parcial"
    assert redes["perfis_com_erro"] == 7
    assert redes["dias_desde_ultima_coleta_ok"] == 1  # parcial grava snapshots: conta como coleta
    assert redes["coletado_em"].startswith(ha_1_dia.strftime("%Y-%m-%dT%H:%M"))


def test_health_status_antigo_sem_perfis_com_erro_vira_zero(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    agora = datetime.now(UTC).isoformat()
    (dir_redes / "status.json").write_text(
        json.dumps({"resultado": "ok", "motivo": None, "coletado_em": agora})
    )
    with _api(dir_redes) as api:
        assert api.get("/api/health").json()["redes"]["perfis_com_erro"] == 0
