"""T-B03: contrato do empacotamento (docs/deploy.md, ADR 0002) verificado nos arquivos."""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[3]
DOCKERFILE = (RAIZ / "apps" / "api" / "Dockerfile").read_text()
COMPOSE = yaml.safe_load((RAIZ / "infra" / "compose.yaml").read_text())
SERVICO = COMPOSE["services"]["api"]


def test_compose_nao_publica_porta_e_entra_na_rede_proxy() -> None:
    assert "ports" not in SERVICO
    assert SERVICO["networks"] == ["proxy"]
    assert COMPOSE["networks"]["proxy"] == {"external": True}


def test_compose_respeita_o_teto_de_recursos_do_servidor() -> None:
    assert str(SERVICO["cpus"]) == "1.0"
    assert SERVICO["mem_limit"] == "2g"
    assert SERVICO["environment"]["ELEICOES_THREADS"] == "2"


def test_compose_monta_datasets_somente_leitura() -> None:
    montagens = [v for v in SERVICO["volumes"] if v.endswith(":/datasets:ro")]
    assert len(montagens) == 1
    assert SERVICO["build"]["platforms"] == ["linux/arm64"]


def test_dockerfile_roda_sem_root_com_factory_e_healthcheck() -> None:
    assert "\nUSER app\n" in DOCKERFILE
    assert '"api.main:app_producao", "--factory"' in DOCKERFILE
    assert '"--port", "8000"' in DOCKERFILE
    assert "HEALTHCHECK" in DOCKERFILE
    assert "/api/health" in DOCKERFILE
    assert DOCKERFILE.count("\nFROM ") >= 2  # multi-stage


def test_threads_aceita_o_nome_do_compose_de_producao(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.config import Settings

    monkeypatch.setenv("ELEICOES_DUCKDB_THREADS", "3")
    assert Settings().threads == 3


def test_candidato_a_presidente_aparece_na_consulta_por_uf() -> None:
    """Presidente só existe como `sg_uf = BR`; filtrar por 'SP' não pode zerar o cargo."""
    from api.repositorio.duckdb import RepositorioDuckDB

    repo = RepositorioDuckDB(RAIZ / "apps" / "api" / "tests" / "fixtures")
    achadas = repo.candidaturas(2026, uf="SP", cargo="PRESIDENTE")
    assert [c.sq_candidato for c in achadas] == [11]
    assert repo.candidaturas(2026, uf="SP", cargo="DEPUTADO FEDERAL")  # outros cargos seguem a UF
