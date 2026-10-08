"""T-B18: API de redes sociais (Instagram) sobre as fixtures Parquet sintéticas.

Mundo da fixture (ver `gerar_fixture.py`): sq 3 tem dois perfis (`ana_alves`, 2 snapshots, 10500
seguidores; `ana_campanha`, 800) e 1000 votos; sq 5 tem perfil indisponível (`bruno_lima`) e 180
votos; sq 7 (`daniel_dias`, 4000 seguidores) tem 700 votos; sq 4 declarou perfil que ainda não foi
coletado; o presidente (sq 11) não declarou Instagram. Posts de `ana_alves`: ver `_POSTS`.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest
from api.config import Settings
from api.main import criar_app
from contratos.modelo import validar
from contratos.redes import REDES_CANDIDATOS, REDES_PERFIS, REDES_POSTS
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
DF = "DEPUTADO FEDERAL"
PARAMS = {"grupo": "missao_2026", "uf": "SP", "cargo": DF}
Json = dict[str, object]


def _settings(dir_dados: Path) -> Settings:
    return Settings(
        dir_dados=dir_dados,
        arquivo_grupos=FIXTURES / "grupos.yaml",
        raiz_repositorio=FIXTURES,
        versao_app="teste",
        aquecer=False,
    )


def _redes(api: TestClient, **extra: object) -> Json:
    r = api.get("/api/redes", params={**PARAMS, **extra})  # type: ignore[arg-type]
    assert r.status_code == 200, r.text
    corpo: Json = r.json()
    return corpo


def _por_sq(corpo: Json) -> dict[int, Json]:
    return {c["sq_candidato"]: c for c in corpo["candidatos"]}  # type: ignore[attr-defined]


def test_fixtures_respeitam_os_contratos_do_dados() -> None:
    validar(pl.read_parquet(FIXTURES / "redes/redes_perfis.parquet"), REDES_PERFIS)
    validar(pl.read_parquet(FIXTURES / "redes/redes_posts.parquet"), REDES_POSTS)
    validar(
        pl.read_parquet(FIXTURES / "redes_candidatos/ano=2026/redes_candidatos.parquet"),
        REDES_CANDIDATOS,
    )


def test_candidato_com_dois_perfis_mostra_ambos_e_analisa_o_maior(api: TestClient) -> None:
    c3 = _por_sq(_redes(api))[3]
    perfis = {p["username"]: p for p in c3["perfis"]}
    assert set(perfis) == {"ana_alves", "ana_campanha"}
    assert perfis["ana_alves"]["principal"] is True  # declarado primeiro ao TSE
    assert perfis["ana_alves"]["analisado"] is True  # mais seguidores
    assert perfis["ana_campanha"]["analisado"] is False
    assert perfis["ana_alves"]["link"] == "https://www.instagram.com/ana_alves/"
    assert perfis["ana_alves"]["seguidores"] == 10500  # último snapshot, não o de 07/10
    assert perfis["ana_alves"]["seguindo"] == 301
    assert perfis["ana_alves"]["n_midias"] == 125
    assert perfis["ana_alves"]["coletado_em"].startswith("2026-10-08T12:00:00")
    assert c3["seguidores"] == 10500
    assert c3["tem_dados"] is True and c3["status"] == "ok"


def test_razoes_seguidores_votos(api: TestClient) -> None:
    c3 = _por_sq(_redes(api))[3]
    assert c3["votos"] == 1000
    assert c3["seguidores_por_mil_votos"] == pytest.approx(10500.0)
    assert c3["votos_por_mil_seguidores"] == pytest.approx(1000 * 1000 / 10500)


def test_perfil_indisponivel_nao_e_zero(api: TestClient) -> None:
    c5 = _por_sq(_redes(api))[5]
    assert c5["status"] == "nao_encontrado"
    assert c5["tem_dados"] is False
    assert c5["seguidores"] is None and c5["votos_por_mil_seguidores"] is None
    assert c5["janelas"] == []
    assert c5["voto_esperado"] is None
    perfil = c5["perfis"][0]
    assert perfil["status"] == "nao_encontrado"
    assert perfil["seguidores"] is None and perfil["seguindo"] is None
    assert perfil["analisado"] is False


def test_janelas_de_posts_e_engajamento(api: TestClient) -> None:
    janelas = {j["janela"]: j for j in _por_sq(_redes(api))[3]["janelas"]}
    assert list(janelas) == ["pre_campanha", "campanha", "pos_eleicao", "total"]
    camp = janelas["campanha"]
    assert camp["n_posts"] == 4  # a4 (04/10 22h em Brasília) ainda é campanha
    assert camp["posts_por_semana"] == pytest.approx(7 * 4 / 50)
    # curtidas nulas (a4) saem do engajamento; (1100, 2200, 3300)/10500 → 10,48 / 20,95 / 31,43 %
    assert camp["n_posts_engajamento"] == 3
    assert camp["engajamento_mediano"] == pytest.approx(100 * 2200 / 10500)
    assert camp["engajamento_medio"] == pytest.approx(100 * (1100 + 2200 + 3300) / 3 / 10500)
    assert janelas["pre_campanha"]["posts_por_semana"] == pytest.approx(7 / 227)
    assert janelas["total"]["n_posts"] == 6
    assert janelas["total"]["pct_video"] == pytest.approx(100 * 2 / 6)  # a1 e a3


def test_pos_eleicao_curto_nao_tem_taxa_semanal(api: TestClient) -> None:
    c3 = _por_sq(_redes(api))[3]
    pos = {j["janela"]: j for j in c3["janelas"]}["pos_eleicao"]
    assert pos["n_posts"] == 1
    assert pos["posts_por_semana"] is None  # < 7 dias de janela: nunca extrapolar
    assert c3["variacao_ritmo_pct"] is None


def test_resumo_do_candidato_usa_campanha(api: TestClient) -> None:
    c3 = _por_sq(_redes(api))[3]
    assert c3["posts_semana_campanha"] == pytest.approx(0.56)
    assert c3["engajamento_mediano"] == pytest.approx(100 * 2200 / 10500)
    assert c3["pct_video"] == pytest.approx(100 / 3)


def test_exclusoes_por_motivo(api: TestClient) -> None:
    corpo = api.get("/api/redes", params={"grupo": "missao_2026"}).json()
    assert corpo["excluidos"] == {
        "sem_instagram": 0,
        "nao_coletado": 1,  # sq 4 declarou, mas a coleta ainda não passou
        "indisponivel": 1,  # sq 5
        "sem_votos": 0,
    }
    assert corpo["agregado"]["n_candidatos"] == 3
    assert corpo["agregado"]["n_com_dados"] == 1
    por_sq = _por_sq(corpo)
    assert por_sq[4]["status"] == "nao_coletado"
    assert por_sq[4]["perfis"][0]["seguidores"] is None


def test_candidato_sem_instagram_declarado(api: TestClient) -> None:
    corpo = api.get("/api/redes", params={"grupo": "novo_2026"}).json()
    assert corpo["excluidos"]["sem_instagram"] == 1
    c = corpo["candidatos"][0]
    assert c["status"] == "sem_rede" and c["perfis"] == [] and c["tem_dados"] is False


def test_agregado_do_grupo(api: TestClient) -> None:
    agg = _redes(api, grupo="mbl_2026")["agregado"]
    assert agg["n_com_dados"] == 2  # sq 3 e sq 7
    assert agg["seguidores_total"] == 14500
    assert agg["mediana_seguidores"] == pytest.approx(7250)


def test_voto_esperado_nulo_com_poucos_candidatos(api: TestClient) -> None:
    # < 10 candidatos com dados no cargo: o ajuste log-log não se sustenta (spec §9.6)
    assert _por_sq(_redes(api))[3]["voto_esperado"] is None


def test_fontes_declaram_instagram_e_tse(api: TestClient) -> None:
    corpo = _redes(api)
    fontes = {f["dataset"]: f for f in corpo["fontes"]}  # type: ignore[attr-defined]
    ig, tse = fontes["redes_perfis"], fontes["rede_social_candidato"]
    assert ig["rotulo"] == "Instagram — API oficial da Meta, coletado em 08/10/2026"
    assert ig["arquivo_oficial_url"].startswith("https://developers.facebook.com/")
    assert tse["arquivo_oficial_url"].endswith("/consulta_cand/rede_social_candidato_2026.zip")
    assert corpo["coletado_em"].startswith("2026-10-08T12:00:00")  # type: ignore[attr-defined]


def test_candidatos_ordenados_por_votos(api: TestClient) -> None:
    corpo = _redes(api, grupo="mbl_2026")
    assert [c["sq_candidato"] for c in corpo["candidatos"]] == [3, 7, 5]  # type: ignore[attr-defined]


def test_foto_e_link_do_tse_acompanham_o_candidato(api: TestClient) -> None:
    c3 = _por_sq(_redes(api))[3]
    assert c3["foto_url"] == "/fotos/2026/3.webp"
    assert c3["link_tse_candidato"]["verificado"] is True


@pytest.mark.parametrize(
    ("params", "status", "codigo"),
    [
        ({"grupo": "mbl_2022"}, 422, "redes_ano_sem_dados"),
        ({"grupo": "nao_existe"}, 422, "grupo_desconhecido"),
        ({"grupo": "missao_2026", "cargo": "REI"}, 422, None),
        ({"grupo": "missao_2026", "uf": "XX"}, 422, None),
        ({}, 422, None),
    ],
)
def test_parametros_invalidos(
    api: TestClient, params: dict[str, str], status: int, codigo: str | None
) -> None:
    r = api.get("/api/redes", params=params)
    assert r.status_code == status
    if codigo:
        assert r.json()["detail"]["codigo"] == codigo


# --- correlações (n < 10 na fixture: ρ nulo, mas n e exclusões contados) -----------------------


def test_correlacoes_com_poucos_candidatos_nao_inventam_rho(api: TestClient) -> None:
    r = api.get("/api/redes/correlacoes", params={**PARAMS, "grupo": "mbl_2026"})
    assert r.status_code == 200, r.text
    (recorte,) = r.json()["recortes"]
    assert recorte["cargo"] == DF and recorte["n_candidatos"] == 3
    pares = {p["id"]: p for p in recorte["pares"]}
    assert list(pares) == ["seguidores_votos", "engajamento_votos", "ritmo_votos"]
    sv = pares["seguidores_votos"]
    assert (sv["n"], sv["n_excluidos"]) == (2, 1)  # sq 3 e 7; sq 5 sem dados
    assert sv["rho"] is None and sv["ic_inf"] is None and sv["ic_sup"] is None
    assert sv["n_minimo"] == 10 and sv["nivel_ic"] == 0.95
    assert recorte["ajuste"] is None


def test_pontos_da_dispersao(api: TestClient) -> None:
    r = api.get("/api/redes/correlacoes", params={**PARAMS, "grupo": "mbl_2026"})
    (recorte,) = r.json()["recortes"]
    pontos = {p["sq_candidato"]: p for p in recorte["pontos"]}
    assert set(pontos) == {3, 7}  # só quem tem seguidores e votos
    p3 = pontos[3]
    assert (p3["seguidores"], p3["votos"], p3["nm_urna"]) == (10500, 1000, "A")
    assert p3["foto_url"] == "/fotos/2026/3.webp"
    assert p3["link"] == "https://www.instagram.com/ana_alves/"
    assert p3["razao_obs_esperado"] is None


def test_correlacoes_sem_cargo_separa_por_cargo(api: TestClient) -> None:
    r = api.get("/api/redes/correlacoes", params={"grupo": "missao_2026"})
    assert [x["cargo"] for x in r.json()["recortes"]] == ["DEPUTADO ESTADUAL", "DEPUTADO FEDERAL"]


def test_correlacoes_por_uf(api: TestClient) -> None:
    r = api.get("/api/redes/correlacoes", params={"grupo": "missao_2026", "por_uf": "true"})
    recortes = {(x["cargo"], x["uf"]) for x in r.json()["recortes"]}
    assert recortes == {("DEPUTADO ESTADUAL", "RJ"), ("DEPUTADO FEDERAL", "SP")}


def test_correlacoes_trazem_fontes_e_aviso_de_causalidade(api: TestClient) -> None:
    corpo = api.get("/api/redes/correlacoes", params=PARAMS).json()
    assert {f["dataset"] for f in corpo["fontes"]} >= {"redes_perfis", "rede_social_candidato"}
    assert "causalidade" in corpo["aviso"].lower()


# --- série de seguidores -----------------------------------------------------------------------


def test_serie_por_candidato_com_dois_snapshots(api: TestClient) -> None:
    r = api.get("/api/redes/serie", params={"sq": 3})
    assert r.status_code == 200, r.text
    alves = {s["username"]: s for s in r.json()["series"]}["ana_alves"]
    assert [p["seguidores"] for p in alves["pontos"]] == [10000, 10500]
    primeiro, segundo = alves["pontos"]
    assert primeiro["delta_abs"] is None and primeiro["dias"] is None
    assert segundo["delta_abs"] == 500
    assert segundo["delta_pct"] == pytest.approx(5.0)
    assert segundo["dias"] == pytest.approx(26 / 24)
    assert alves["resumo"]["n_snapshots"] == 2 and alves["resumo"]["delta_abs"] == 500


def test_serie_com_um_snapshot_nao_tem_variacao(api: TestClient) -> None:
    series = api.get("/api/redes/serie", params={"sq": 3}).json()["series"]
    campanha = {s["username"]: s for s in series}["ana_campanha"]
    assert len(campanha["pontos"]) == 1
    assert campanha["resumo"]["n_snapshots"] == 1
    assert campanha["resumo"]["delta_abs"] is None and campanha["resumo"]["delta_pct"] is None


def test_serie_por_username(api: TestClient) -> None:
    corpo = api.get("/api/redes/serie", params={"username": "daniel_dias"}).json()
    assert [s["username"] for s in corpo["series"]] == ["daniel_dias"]
    assert corpo["series"][0]["link"] == "https://www.instagram.com/daniel_dias/"
    assert "08/10/2026" in corpo["aviso"]  # a série só existe a partir da primeira coleta


@pytest.mark.parametrize(
    ("params", "status", "codigo"),
    [
        ({"sq": 5}, 404, "redes_sem_serie"),  # só perfil indisponível: nenhum ponto
        ({"sq": 4}, 404, "redes_sem_serie"),  # declarado, nunca coletado
        ({"sq": 999}, 404, "candidato_nao_encontrado"),
        ({"username": "ninguem"}, 404, "redes_sem_serie"),
        ({}, 422, "alvo_ambiguo"),
        ({"sq": 3, "username": "ana_alves"}, 422, "alvo_ambiguo"),
        ({"username": "Nome Inválido!"}, 422, None),
    ],
)
def test_serie_erros(
    api: TestClient, params: dict[str, object], status: int, codigo: str | None
) -> None:
    r = api.get("/api/redes/serie", params=params)  # type: ignore[arg-type]
    assert r.status_code == status
    if codigo:
        assert r.json()["detail"]["codigo"] == codigo


# --- ficha -------------------------------------------------------------------------------------


def test_ficha_traz_bloco_redes(api: TestClient) -> None:
    redes = api.get("/api/candidatos/2026/3").json()["redes"]
    assert {p["username"] for p in redes["perfis"]} == {"ana_alves", "ana_campanha"}
    alves = next(p for p in redes["perfis"] if p["username"] == "ana_alves")
    assert alves["seguidores"] == 10500 and alves["analisado"] is True
    assert redes["coletado_em"].startswith("2026-10-08")
    assert {f["dataset"] for f in redes["fontes"]} == {"redes_perfis", "rede_social_candidato"}


def test_ficha_com_perfil_indisponivel_e_sem_declaracao(api: TestClient) -> None:
    indisponivel = api.get("/api/candidatos/2026/5").json()["redes"]
    assert indisponivel["perfis"][0]["status"] == "nao_encontrado"
    assert indisponivel["perfis"][0]["seguidores"] is None
    sem = api.get("/api/candidatos/2026/11").json()["redes"]
    assert sem["perfis"] == []  # não declarou Instagram ao TSE (≠ dado ausente)


def test_ficha_de_2022_nao_tem_redes(api: TestClient) -> None:
    assert api.get("/api/candidatos/2022/1").json()["redes"] is None


# --- dado de redes não publicado -----------------------------------------------------------------


@pytest.fixture
def api_sem_redes(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """App sobre uma cópia da fixture sem os datasets de redes."""
    destino = tmp_path_factory.mktemp("sem_redes")
    shutil.copytree(FIXTURES, destino, dirs_exist_ok=True, ignore=shutil.ignore_patterns("redes*"))
    cfg = _settings(destino)
    with TestClient(criar_app(cfg)) as cliente:
        yield cliente


@pytest.mark.parametrize("caminho", ["/api/redes", "/api/redes/correlacoes"])
def test_sem_dado_de_redes_o_erro_e_claro(api_sem_redes: TestClient, caminho: str) -> None:
    r = api_sem_redes.get(caminho, params=PARAMS)
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "redes_indisponiveis"
    assert "redes sociais" in r.json()["detail"]["mensagem"]


def test_serie_sem_dado_de_redes(api_sem_redes: TestClient) -> None:
    r = api_sem_redes.get("/api/redes/serie", params={"sq": 3})
    assert r.status_code == 503 and r.json()["detail"]["codigo"] == "redes_indisponiveis"


def test_ficha_continua_funcionando_sem_redes(api_sem_redes: TestClient) -> None:
    r = api_sem_redes.get("/api/candidatos/2026/3")
    assert r.status_code == 200 and r.json()["redes"] is None


def test_versao_dos_dados_acompanha_a_coleta_de_redes(
    api: TestClient, api_sem_redes: TestClient
) -> None:
    com = api.app.state.repositorio.versao_dados()  # type: ignore[attr-defined]
    sem = api_sem_redes.app.state.repositorio.versao_dados()  # type: ignore[attr-defined]
    assert com.startswith(sem) and "2026-10-08T12:00:00" in com
    assert sem == api_sem_redes.app.state.repositorio.dt_geracao()  # type: ignore[attr-defined]


# --- contrato ----------------------------------------------------------------------------------


def test_openapi_documenta_redes() -> None:
    doc = criar_app(_settings(FIXTURES)).openapi()
    for caminho in ("/api/redes", "/api/redes/correlacoes", "/api/redes/serie"):
        assert caminho in doc["paths"]
    esquemas = doc["components"]["schemas"]
    assert "redes" in esquemas["FichaCandidato"]["properties"]
    assert {"Redes", "Correlacoes", "SerieRedes"} <= set(esquemas)
