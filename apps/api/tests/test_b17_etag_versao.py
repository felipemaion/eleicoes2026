"""T-B17: o ETag muda com a versão do build, mesmo com o mesmo DT_GERACAO."""

from pathlib import Path

import pytest
from api.config import Settings, obter_settings
from api.main import app_producao, criar_app
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
URL = "/api/candidatos/ufs?ano=2026&cargo=PRESIDENTE"


def settings_fixture() -> Settings:
    return Settings(
        dir_dados=FIXTURES,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        aquecer=False,
    )


def _etag(versao: str, url: str = URL) -> str:
    cfg = settings_fixture().model_copy(update={"versao_app": versao})
    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get(url)
        assert resposta.status_code == 200
        return resposta.headers["etag"]


def test_versoes_diferentes_geram_etags_diferentes_sem_304() -> None:
    antigo = _etag("sha-antigo")
    cfg = settings_fixture().model_copy(update={"versao_app": "sha-novo"})
    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get(URL, headers={"If-None-Match": antigo})
    assert resposta.status_code == 200
    assert resposta.headers["etag"] != antigo


def test_mesma_versao_continua_dando_304() -> None:
    etag = _etag("sha-x")
    cfg = settings_fixture().model_copy(update={"versao_app": "sha-x"})
    with TestClient(criar_app(cfg)) as cliente:
        resposta = cliente.get(URL, headers={"If-None-Match": etag})
    assert resposta.status_code == 304


def test_health_expoe_versao_real() -> None:
    cfg = settings_fixture().model_copy(update={"versao_app": "abc123"})
    with TestClient(criar_app(cfg)) as cliente:
        assert cliente.get("/api/health").json()["versao"] == "abc123"


def test_sem_versao_falha_alto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEICOES_VERSAO_APP", raising=False)
    obter_settings.cache_clear()  # app_producao lê o Settings memoizado
    with pytest.raises(RuntimeError, match="VERSAO_APP"):
        criar_app(Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="VERSAO_APP"):
        app_producao()
    obter_settings.cache_clear()
