"""T-B19: série de redes em diretório próprio, recarga por mtime e status da última coleta.

DuckDB real sobre as fixtures Parquet; o diretório de redes é copiado para `tmp_path`, separado de
`dir_dados`, como no servidor (`/redes:ro` ao lado de `/datasets:ro`).
"""

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from api.config import Settings
from api.main import criar_app
from api.repositorio.duckdb import RepositorioDuckDB
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
PARAMS = {"grupo": "missao_2026", "cargo": "DEPUTADO FEDERAL", "uf": "SP"}


def _copiar_redes(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    for nome in ("redes_perfis.parquet", "redes_posts.parquet"):
        shutil.copy(FIXTURES / "redes" / nome, destino / nome)
    return destino


def _manifesto(dir_redes: Path, mtime: float) -> None:
    arquivo = dir_redes / "manifesto.json"
    arquivo.write_text("{}")
    os.utime(arquivo, (mtime, mtime))


def _status(dir_redes: Path, **campos: object) -> None:
    (dir_redes / "status.json").write_text(json.dumps(campos))


def _api(dir_redes: Path, **extra: object) -> TestClient:
    cfg = Settings(
        dir_dados=FIXTURES,
        redes_dir=dir_redes,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        versao_app="teste",
        aquecer=False,
        **extra,  # type: ignore[arg-type]
    )
    return TestClient(criar_app(cfg))


class Relogio:
    """Relógio manual: o teste controla o intervalo de 1 verificação por minuto."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


# --- diretório separado ---------------------------------------------------------------------


def test_le_perfis_e_posts_do_diretorio_configurado(tmp_path: Path) -> None:
    repo = RepositorioDuckDB(FIXTURES, dir_redes=_copiar_redes(tmp_path / "redes"))
    meta = repo.redes_meta()
    assert meta is not None
    assert meta.coletado_em == datetime(2026, 10, 8, 12, tzinfo=UTC)


def test_diretorio_vazio_nao_cai_na_fixture_de_dir_dados(tmp_path: Path) -> None:
    (tmp_path / "vazio").mkdir()
    repo = RepositorioDuckDB(FIXTURES, dir_redes=tmp_path / "vazio")
    assert repo.redes_meta() is None


def test_padrao_continua_sendo_a_subpasta_de_dir_dados() -> None:
    assert RepositorioDuckDB(FIXTURES).redes_meta() is not None


def test_settings_le_a_variavel_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEICOES_REDES_DIR", "/redes")
    assert Settings(dir_dados=Path("/datasets")).redes_dir == Path("/redes")
    monkeypatch.delenv("ELEICOES_REDES_DIR")
    assert Settings(dir_dados=Path("/datasets")).redes_dir is None


# --- recarga por mtime ----------------------------------------------------------------------


def test_recarrega_quando_a_coleta_promove_dados_novos(tmp_path: Path) -> None:
    dir_redes = tmp_path / "redes"
    dir_redes.mkdir()
    relogio = Relogio()
    repo = RepositorioDuckDB(FIXTURES, dir_redes=dir_redes, relogio=relogio)
    assert repo.redes_meta() is None
    sem_redes = repo.versao_dados()

    _copiar_redes(dir_redes)
    _manifesto(dir_redes, 1_700_000_000)
    assert repo.redes_meta() is None  # dentro do intervalo: nem olha o disco
    assert repo.versao_dados() == sem_redes

    relogio.agora += 61
    meta = repo.redes_meta()
    assert meta is not None
    assert repo.versao_dados() != sem_redes
    assert repo.redes_perfis(2026, sqs=[3])  # as views passaram a enxergar o dado novo


def test_nova_coleta_muda_a_versao_e_so_depois_do_intervalo(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    _manifesto(dir_redes, 1_700_000_000)
    relogio = Relogio()
    repo = RepositorioDuckDB(FIXTURES, dir_redes=dir_redes, relogio=relogio)
    antes = repo.versao_dados()

    perfis = pl.read_parquet(dir_redes / "redes_perfis.parquet")
    novo = perfis.with_columns(pl.col("coletado_em") + pl.duration(days=1))
    novo.write_parquet(dir_redes / "redes_perfis.parquet")
    _manifesto(dir_redes, 1_700_000_100)

    relogio.agora += 30
    assert repo.versao_dados() == antes  # no máximo 1 verificação por intervalo
    relogio.agora += 31
    assert repo.versao_dados() != antes
    meta = repo.redes_meta()
    assert meta is not None
    assert meta.coletado_em == datetime(2026, 10, 9, 12, tzinfo=UTC)


def test_sem_mudanca_de_mtime_nao_reabre(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    _manifesto(dir_redes, 1_700_000_000)
    relogio = Relogio()
    repo = RepositorioDuckDB(FIXTURES, dir_redes=dir_redes, relogio=relogio)
    assert repo.recargas_redes == 0
    relogio.agora += 120
    repo.versao_dados()
    assert repo.recargas_redes == 0


def test_etag_de_redes_muda_apos_a_recarga(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    _manifesto(dir_redes, 1_700_000_000)
    with _api(dir_redes, redes_recarga_s=0) as api:
        r1 = api.get("/api/redes", params=PARAMS)
        assert r1.status_code == 200
        perfis = pl.read_parquet(dir_redes / "redes_perfis.parquet")
        perfis.with_columns(pl.col("coletado_em") + pl.duration(days=1)).write_parquet(
            dir_redes / "redes_perfis.parquet"
        )
        _manifesto(dir_redes, 1_700_000_100)
        r2 = api.get("/api/redes", params=PARAMS, headers={"If-None-Match": r1.headers["etag"]})
    assert r2.status_code == 200  # não é 304: o dado mudou
    assert r2.headers["etag"] != r1.headers["etag"]
    assert r2.json()["coletado_em"].startswith("2026-10-09")


def test_recarga_com_arquivo_quebrado_mantem_o_anterior_e_tenta_de_novo(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    _manifesto(dir_redes, 1_700_000_000)
    relogio = Relogio()
    repo = RepositorioDuckDB(FIXTURES, dir_redes=dir_redes, relogio=relogio)
    antes = repo.redes_meta()

    (dir_redes / "redes_perfis.parquet").write_bytes(b"lixo")
    _manifesto(dir_redes, 1_700_000_100)
    relogio.agora += 61
    assert repo.redes_meta() == antes  # serve o último estado bom, sem derrubar a API

    _copiar_redes(dir_redes)
    _manifesto(dir_redes, 1_700_000_200)
    relogio.agora += 61
    assert repo.redes_meta() == antes
    assert repo.recargas_redes >= 1


# --- status da última coleta ----------------------------------------------------------------


def test_health_sem_status_nem_dados_de_redes_tem_redes_nulo(tmp_path: Path) -> None:
    (tmp_path / "vazio").mkdir()
    with _api(tmp_path / "vazio") as api:
        corpo = api.get("/api/health").json()
    assert corpo["status"] == "ok"
    assert corpo["redes"] is None


def test_health_sem_status_json_usa_a_coleta_dos_dados(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    with _api(dir_redes) as api:
        redes = api.get("/api/health").json()["redes"]
    assert redes["coletado_em"].startswith("2026-10-08T12:00")
    assert redes["resultado"] is None
    assert redes["motivo"] is None
    assert redes["dias_desde_ultima_coleta_ok"] >= 6  # dado de 08/10, hoje é ≥ 14/10


def test_health_status_ok(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    ha_3_dias = datetime.now(UTC) - timedelta(days=3, hours=2)
    _status(
        dir_redes,
        inicio=(ha_3_dias - timedelta(minutes=4)).isoformat(),
        fim=ha_3_dias.isoformat(),
        resultado="ok",
        motivo=None,
        perfis_coletados=42,
        coletado_em=ha_3_dias.isoformat(),
    )
    with _api(dir_redes) as api:
        redes = api.get("/api/health").json()["redes"]
    assert redes["resultado"] == "ok"
    assert redes["motivo"] is None
    assert redes["dias_desde_ultima_coleta_ok"] == 3
    assert redes["coletado_em"].startswith(ha_3_dias.strftime("%Y-%m-%dT%H:%M"))


def test_health_status_erro_conta_dias_da_ultima_coleta_boa(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    agora = datetime.now(UTC)
    _status(
        dir_redes,
        inicio=agora.isoformat(),
        fim=agora.isoformat(),
        resultado="erro",
        motivo="token vencido",
        perfis_coletados=0,
        coletado_em=agora.isoformat(),
    )
    with _api(dir_redes) as api:
        redes = api.get("/api/health").json()["redes"]
    assert redes["resultado"] == "erro"
    assert redes["motivo"] == "token vencido"
    # a tentativa falhou: os dias contam desde a última coleta que entrou nos dados (08/10)
    assert redes["dias_desde_ultima_coleta_ok"] >= 6
    assert redes["coletado_em"].startswith("2026-10-08T12:00")


def test_health_status_ilegivel_nao_derruba_a_api(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    (dir_redes / "status.json").write_text("{não é json")
    with _api(dir_redes) as api:
        r = api.get("/api/health")
    assert r.status_code == 200
    assert r.json()["redes"]["resultado"] is None


def test_health_reflete_o_status_novo_sem_reiniciar(tmp_path: Path) -> None:
    dir_redes = _copiar_redes(tmp_path / "redes")
    with _api(dir_redes) as api:
        assert api.get("/api/health").json()["redes"]["resultado"] is None
        agora = datetime.now(UTC).isoformat()
        _status(dir_redes, resultado="limite", motivo="rate limit", coletado_em=agora)
        assert api.get("/api/health").json()["redes"]["resultado"] == "limite"
