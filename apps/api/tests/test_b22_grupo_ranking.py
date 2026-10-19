"""T-B22: grupo por `ranking` (cargo+UF) não pode derrubar as rotas que percorrem todos os grupos.

Regressão da T-B20: `/municipios/{ibge}` dava 422 em produção porque o laço sobre o catálogo
chamava `candidaturas_do_grupo` num grupo de ranking. Aqui o catálogo é o `config/grupos.yaml` real.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures"
MUNDO_REF = Path(__file__).parent / "fixtures_referencias"
SP_MUN = 3550308


def _cfg(grupos: Path, dados: Path, raiz: Path | None = None, **extra: object) -> Settings:
    return Settings(
        dir_dados=dados,
        arquivo_grupos=grupos,
        raiz_repositorio=raiz or dados,
        versao_app="teste",
        **extra,  # type: ignore[arg-type]
    )


@pytest.fixture
def real() -> Iterator[TestClient]:
    """Catálogo real do repositório (tem grupo de ranking) sobre os Parquet de teste."""
    with TestClient(
        criar_app(_cfg(RAIZ / "config" / "grupos.yaml", FIXTURES, RAIZ, aquecer=False))
    ) as c:
        yield c


def test_catalogo_real_tem_grupo_de_ranking(real: TestClient) -> None:
    assert any(g.ranking for g in real.app.state.catalogo.grupos.values())  # type: ignore[attr-defined]


def test_municipio_com_catalogo_real_responde_200_sem_o_ranking(real: TestClient) -> None:
    r = real.get(f"/api/municipios/{SP_MUN}")
    assert r.status_code == 200, r.text
    ids = {g["id"] for g in r.json()["grupos"]}
    assert "top5_eleitos_outros_2026" not in ids
    assert ids  # os demais grupos continuam


def test_municipio_no_mundo_de_referencias_nao_inclui_ranking() -> None:
    cfg = _cfg(MUNDO_REF / "grupos.yaml", MUNDO_REF, aquecer=False)
    with TestClient(criar_app(cfg)) as c:
        r = c.get(f"/api/municipios/{SP_MUN}")
        assert r.status_code == 200, r.text
        assert "top5_eleitos_outros_2026" not in {g["id"] for g in r.json()["grupos"]}


def test_aquecimento_com_catalogo_real_segue_e_nao_aquece_o_ranking() -> None:
    cfg = _cfg(RAIZ / "config" / "grupos.yaml", FIXTURES, RAIZ, aquecer=True)
    with TestClient(criar_app(cfg)) as c:
        aq = c.app.state.aquecimento  # type: ignore[attr-defined]
        aq.join(timeout=60)
        # Comparativos podem falhar aqui (MBL real não existe nas fixtures); o plano segue.
        assert aq.aquecidas > 0
        assert not any("top5_eleitos" in nome for nome, _ in aq._plano())


def test_rotas_que_percorrem_grupos_com_catalogo_real(real: TestClient) -> None:
    """Pega a próxima regressão do mesmo tipo: só o ranking recusa."""
    assert real.get("/api/grupos").status_code == 200
    assert real.get(f"/api/municipios/{SP_MUN}").status_code == 200
    for g in real.app.state.catalogo.grupos.values():  # type: ignore[attr-defined]
        esperado = 422 if g.ranking else 200
        r = real.get("/api/candidatos", params={"grupo": g.id, "cargo": "DEPUTADO FEDERAL"})
        assert r.status_code == esperado, (g.id, r.text)
