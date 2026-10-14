"""T-B20: GET /api/referencias — nossos candidatos × grupo de referência, lado a lado.

Mundo à parte (`fixtures_referencias`, gerado por `gerar_fixture.py`): Dep. Estadual SP com
Missão 21 (3000 votos, eleito) e 20 (300, sem contas); outros partidos eleitos 22 e 23 (empate em
1500 → desempate por sq), 24 (900), 25 (800), 26 (700), 27 (650, 6º: corta); 28 (4000) não foi
eleito. Só o 22 tem contas (T-D10 ainda não publicou as dos demais). RJ-DE: só o Missão (sem
eleito de outro partido). Presidente: Missão 12; referência 14 (3800), 11 (3700), 13 (3600).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from api.config import Settings
from api.main import criar_app
from fastapi.testclient import TestClient

DE, PR = "DEPUTADO ESTADUAL", "PRESIDENTE"
MUNDO = Path(__file__).parent / "fixtures_referencias"


@pytest.fixture
def ref() -> Iterator[TestClient]:
    """App real (DuckDB sobre Parquet) no mundo de referências."""
    cfg = Settings(
        dir_dados=MUNDO,
        arquivo_grupos=MUNDO / "grupos.yaml",
        raiz_repositorio=MUNDO,
        versao_app="teste",
        aquecer=False,
    )
    with TestClient(criar_app(cfg)) as cliente:
        yield cliente


def _get(c: TestClient, **params: object) -> dict[str, object]:
    r = c.get("/api/referencias", params=params)
    assert r.status_code == 200, r.text
    corpo: dict[str, object] = r.json()
    return corpo


def _sqs(lado: dict[str, object]) -> list[int]:
    return [c["sq_candidato"] for c in lado["candidatos"]]  # type: ignore[index, attr-defined]


def test_deputado_estadual_top5_de_outros_partidos(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="SP")
    assert _sqs(corpo["nossos"]) == [21, 20]  # type: ignore[arg-type]
    # 22 e 23 empatam (1500): menor sq primeiro; 27 (6º), 28 (não eleito) e 21 (Missão) fora.
    assert _sqs(corpo["referencia"]) == [22, 23, 24, 25, 26]  # type: ignore[arg-type]
    assert corpo["rotulo"] == (
        "Missão · Dep. estadual · SP × 5 eleitos mais votados de outros partidos em SP"
    )
    assert corpo["ano"] == 2026
    assert corpo["cargo"] == DE
    assert corpo["uf"] == "SP"


def test_candidato_traz_foto_partido_resultado_e_indicadores(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="SP")
    x1 = corpo["referencia"]["candidatos"][0]  # type: ignore[index]
    assert x1["foto_url"] == "/fotos/2026/22.webp"
    assert x1["partido"] == {"numero": 22, "sigla": "PL"}
    assert x1["resultado"] == "ELEITO POR QP"
    ind = x1["indicadores"]
    assert ind["votos"] == 1500
    assert ind["pct_validos"] == pytest.approx(1500 / 12400 * 100)
    assert ind["penetracao"] == pytest.approx(1500 / 17500 * 1000)
    assert ind["n_municipios"] == 2
    assert 0 < ind["hhi"] <= 1
    assert ind["custo_voto_pago"] == pytest.approx(36000 / 1500)
    assert ind["receita_total"] == pytest.approx(40000.0)
    assert ind["pct_publico"] == pytest.approx(75.0)
    assert x1["motivos"] == {}  # nada nulo: nada a explicar


def test_candidato_sem_financas_vem_nulo_com_motivo_nunca_zero(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="SP")
    x2 = corpo["referencia"]["candidatos"][1]  # type: ignore[index]
    assert x2["sq_candidato"] == 23
    ind = x2["indicadores"]
    assert ind["votos"] == 1500  # votos seguem
    for campo in ("custo_voto_pago", "receita_total", "pct_publico", "pct_pessoa_fisica"):
        assert ind[campo] is None, campo
        assert "contas" in x2["motivos"][campo]
    m1 = corpo["nossos"]["candidatos"][1]  # type: ignore[index]
    assert m1["sq_candidato"] == 20
    assert m1["indicadores"]["custo_voto_pago"] is None


def test_mediana_da_referencia_ignora_nulos_e_diz_quantos(ref: TestClient) -> None:
    ref_lado = _get(ref, cargo=DE, uf="SP")["referencia"]
    med = ref_lado["mediana"]  # type: ignore[index]
    assert med["votos"] == 900  # mediana de [1500, 1500, 900, 800, 700]
    assert med["custo_voto_pago"] == pytest.approx(24.0)  # só o 22 tem contas
    assert ref_lado["n_mediana"]["votos"] == 5  # type: ignore[index]
    assert ref_lado["n_mediana"]["custo_voto_pago"] == 1  # type: ignore[index]


def test_indices_relativos_a_mediana_so_nos_nossos(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="SP")
    m2, m1 = corpo["nossos"]["candidatos"]  # type: ignore[index]
    assert m2["indices"]["votos"] == pytest.approx(3000 / 900)
    assert m1["indices"]["votos"] == pytest.approx(300 / 900)
    assert m2["indices"]["custo_voto_pago"] == pytest.approx((4000 / 3000) / 24.0)
    assert m1["indices"]["custo_voto_pago"] is None  # nosso sem contas
    assert "custo_voto_pago" in m1["motivos"]
    assert all(c["indices"] is None for c in corpo["referencia"]["candidatos"])  # type: ignore[index]


def test_destaque_marca_o_candidato_pedido(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="SP", sq=20)
    marcados = [c["sq_candidato"] for c in corpo["nossos"]["candidatos"] if c["destacado"]]  # type: ignore[index]
    assert marcados == [20]
    assert corpo["destaque"] == 20


def test_destaque_fora_dos_nossos_e_422(ref: TestClient) -> None:
    r = ref.get("/api/referencias", params={"cargo": DE, "uf": "SP", "sq": 22})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "sq_fora_dos_nossos"


def test_uf_sem_eleito_de_outro_partido_nao_inventa_referencia(ref: TestClient) -> None:
    corpo = _get(ref, cargo=DE, uf="RJ")
    assert _sqs(corpo["nossos"]) == [4]  # type: ignore[arg-type]
    lado = corpo["referencia"]
    assert lado["candidatos"] == []  # type: ignore[index]
    assert lado["motivo_vazio"]  # type: ignore[index]
    assert all(v is None for v in lado["mediana"].values())  # type: ignore[index, union-attr]
    assert all(v is None for v in corpo["nossos"]["candidatos"][0]["indices"].values())  # type: ignore[index]


def test_presidente_usa_grupo_por_lista_e_ignora_uf(ref: TestClient) -> None:
    corpo = _get(ref, cargo=PR, uf="SP")
    assert corpo["uf"] is None
    assert _sqs(corpo["nossos"]) == [12]  # type: ignore[arg-type]
    assert _sqs(corpo["referencia"]) == [14, 11, 13]  # type: ignore[arg-type]  # ordem por votos
    assert corpo["rotulo"] == "Q (MISSÃO) × 3 presidenciáveis"
    assert corpo["referencia"]["candidatos"][1]["indicadores"]["votos"] == 3700  # type: ignore[index]  # com exterior


def test_validacao_dos_parametros(ref: TestClient) -> None:
    assert ref.get("/api/referencias").status_code == 422  # cargo obrigatório
    r = ref.get("/api/referencias", params={"cargo": DE})  # DE exige UF
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "uf_obrigatoria"
    r = ref.get("/api/referencias", params={"cargo": "SENADOR", "uf": "SP"})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "cargo_sem_referencia"
    assert ref.get("/api/referencias", params={"cargo": DE, "uf": "XX"}).status_code == 422


def test_grupos_de_referencia_nao_poluem_listas_de_filtro(ref: TestClient) -> None:
    ids = {g["id"] for g in ref.get("/api/grupos").json()["grupos"]}
    assert ids == {"missao_2026"}
    assert {g["id"] for g in ref.get("/api/meta").json()["grupos"]} == {"missao_2026"}


def test_grupo_por_ranking_nao_vira_lista_de_candidatos(ref: TestClient) -> None:
    r = ref.get("/api/candidatos", params={"grupo": "top5_eleitos_outros_2026", "cargo": DE})
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "grupo_por_ranking"


def test_cache_http_e_openapi(ref: TestClient) -> None:
    r = ref.get("/api/referencias", params={"cargo": DE, "uf": "SP"})
    assert r.headers["etag"]
    assert (
        ref.get(
            "/api/referencias",
            params={"cargo": DE, "uf": "SP"},
            headers={"If-None-Match": r.headers["etag"]},
        ).status_code
        == 304
    )
    assert "/api/referencias" in ref.get("/openapi.json").json()["paths"]


def test_contas_de_quem_foi_ao_2o_turno_nao_somem(ref: TestClient) -> None:
    """sq 14 só tem prestação com nr_turno=2 (cumulativa): não pode virar `gastos: null`."""
    ficha = ref.get("/api/candidatos/2026/14").json()
    assert ficha["gastos"] is not None
    assert ficha["gastos"]["despesa_contratada"] == 76000.0
    assert ficha["gastos"]["custo_voto_pago"] == pytest.approx(76000 / 3800)
    assert ficha["receitas"]["receita_total"] == 90000.0
