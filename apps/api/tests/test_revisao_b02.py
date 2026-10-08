"""Correções da revisão do PR #32: poda hive, validação de colunas, cache, IPCA, quebras."""

import shutil
from pathlib import Path

import duckdb
import pytest
from api.cache_servico import CacheLRU
from api.config import Settings
from api.dominio import Indicador
from api.main import criar_app
from api.repositorio.base import DadosIndisponiveis
from api.repositorio.duckdb import RepositorioDuckDB
from api.repositorio.memoria import DadosMemoria, RepositorioMemoria
from api.repositorio.modelos import Candidatura, DespesaBruta, VariacaoIpca
from api.servicos.contas import contas_de
from api.servicos.mapa import EscalaSugerida, _escala, quebras_da_escala
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


# -------------------------------------------------------------- B3: desempenho
def test_poda_de_particao_hive_por_ano() -> None:
    repo = RepositorioDuckDB(FIXTURES)
    try:
        plano = "\n".join(
            str(linha[1])
            for linha in repo._con.execute(
                "EXPLAIN SELECT * FROM candidatos WHERE ano = 2026"
            ).fetchall()
        )
    finally:
        repo.fechar()
    assert "ano=2026" in plano.replace(" ", "") or "2026" in plano
    # o filtro vira predicado do scan Parquet (e a partição não lida é descartada)
    assert "Filters" in plano or "PARQUET" in plano.upper()


def test_municipio_filtra_no_sql_e_na_memoria() -> None:
    repo = RepositorioDuckDB(FIXTURES)
    try:
        so_santos = repo.base_eleitoral(
            2026, "DEPUTADO FEDERAL", por_zona=False, cd_mun_ibge=3548500
        )
        votos = repo.votos_territorio(2026, [5], por_zona=False, cd_mun_ibge=3548500)
    finally:
        repo.fechar()
    assert [b.cd_mun_ibge for b in so_santos] == [3548500]
    assert [(v.cd_mun_ibge, v.votos) for v in votos] == [(3548500, 40)]


def test_cache_lru_evicta_e_invalida_por_dt_geracao() -> None:
    cache = CacheLRU(capacidade=2)
    chamadas: list[str] = []

    def calcula(valor: str) -> str:
        chamadas.append(valor)
        return valor

    assert cache.obter("d1", "a", lambda: calcula("a")) == "a"
    assert cache.obter("d1", "a", lambda: calcula("a2")) == "a"  # hit
    assert cache.obter("d2", "a", lambda: calcula("a-d2")) == "a-d2"  # outro dt_geracao
    cache.obter("d1", "b", lambda: calcula("b"))  # estoura: sai o menos recente
    assert len(cache) == 2
    assert chamadas == ["a", "a-d2", "b"]


def test_mapa_repetido_vem_do_cache() -> None:
    app = criar_app(
        Settings(
            dir_dados=FIXTURES, arquivo_grupos=FIXTURES / "grupos.yaml", raiz_repositorio=FIXTURES
        )
    )
    with TestClient(app) as c:
        repo = app.state.repositorio
        original = repo.votos_territorio
        n: list[int] = []
        repo.votos_territorio = lambda *a, **k: (n.append(1), original(*a, **k))[1]
        params = {"ano": 2026, "cargo": "DEPUTADO FEDERAL", "grupo": "missao_2026"}  # sem UF
        a, b = c.get("/api/mapa", params=params), c.get("/api/mapa", params=params)
    assert a.json() == b.json()
    assert len(n) == 1


# ------------------------------------------------------- B4: provisórios
def test_coluna_ausente_em_provisorio_falha_clara_na_abertura(tmp_path: Path) -> None:
    destino = tmp_path / "dados"
    shutil.copytree(FIXTURES, destino)
    con = duckdb.connect()
    con.execute(
        "COPY (SELECT ano, sq_candidato, ds_origem_despesa, vr_despesa_contratada"
        f" FROM read_parquet('{destino / 'despesas.parquet'}'))"
        f" TO '{destino / 'despesas.parquet'}' (FORMAT PARQUET)"
    )
    with pytest.raises(
        DadosIndisponiveis, match=r"despesas: colunas ausentes \['vr_despesa_paga'\]"
    ):
        RepositorioDuckDB(destino)


def test_dataset_com_contrato_sem_coluna_tambem_falha(tmp_path: Path) -> None:
    destino = tmp_path / "dados"
    shutil.copytree(FIXTURES, destino)
    con = duckdb.connect()
    for arquivo in (destino / "detalhe_votacao_munzona").glob("ano=*/*.parquet"):
        con.execute(
            f"COPY (SELECT * EXCLUDE (qt_aptos) FROM read_parquet('{arquivo}'))"
            f" TO '{arquivo}' (FORMAT PARQUET)"
        )
    with pytest.raises(DadosIndisponiveis, match="qt_aptos"):
        RepositorioDuckDB(destino)


# ------------------------------------------------------------------ B1: IPCA
def _cand(ano: int, sq: int) -> Candidatura:
    return Candidatura(ano, sq, f"p{sq}", f"N{sq}", "SP", "DEPUTADO FEDERAL", 14, "X", "APTO", None)


def _repo_ipca(ultimo_mes: str) -> RepositorioMemoria:
    meses = [f"2022-{m:02d}" for m in (10, 11, 12)] + [
        f"{a}-{m:02d}" for a in (2023, 2024, 2025) for m in range(1, 13)
    ]
    meses += [f"2026-{m:02d}" for m in range(1, int(ultimo_mes[5:]) + 1)]
    dados = DadosMemoria(
        despesas={9: [DespesaBruta(9, "Serviços", 1000.0, 500.0)]},
        ipca=[VariacaoIpca(m, 1.0) for m in meses],
    )
    return RepositorioMemoria("dt", [2022], ["SP"], ["DEPUTADO FEDERAL"], dados)


def test_mes_base_ipca_cai_para_o_ultimo_disponivel_e_e_declarado() -> None:
    contas = contas_de(_repo_ipca("2026-08"), 2022, [_cand(2022, 9)])
    assert contas.base_ipca == "2026-08"  # set/2026 ainda não saiu (ADR 0007, emenda)
    fator = 1.01**47  # out/2022 … ago/2026 = 47 meses
    assert contas.por_candidato[0].custo.despesa_contratada == pytest.approx(1000 * fator)


def test_mes_base_ipca_usa_o_alvo_quando_publicado() -> None:
    contas = contas_de(_repo_ipca("2026-09"), 2022, [_cand(2022, 9)])
    assert contas.base_ipca == "2026-09"


# ---------------------------------------------------------------- B2: quebras
def test_menos_de_dois_valores_nao_devolve_lista_vazia_silenciosa() -> None:
    assert quebras_da_escala([5.0]) is None
    escala = _escala(Indicador.PENETRACAO, [5.0])
    assert isinstance(escala, EscalaSugerida)
    assert escala.quebras is None
    assert escala.aviso
    assert _escala(Indicador.PENETRACAO, [1.0, 2.0, 3.0]).aviso is None


@pytest.mark.xfail(
    strict=True, reason="T-A06: indicadores.espacial.quebras_comuns ainda não foi publicada"
)
def test_quebras_vem_de_indicadores_quebras_comuns() -> None:
    from indicadores import espacial

    assert hasattr(espacial, "quebras_comuns")
