"""T-B03: escala sequencial com quebras comuns 2022+2026 (spec §8.2) em /mapa e /comparativo."""

from pathlib import Path

import pytest
from api.dominio import Cargo, Indicador, Nivel
from api.repositorio.memoria import DadosMemoria, EleitoradoMemoria, RepositorioMemoria, VotoMemoria
from api.repositorio.modelos import Candidatura, Municipio
from api.servicos.comparativo import montar_comparativo
from api.servicos.grupos import Catalogo, carregar_catalogo
from api.servicos.mapa import Mapa, montar_mapa

DF = "DEPUTADO FEDERAL"
MUNICIPIOS = [3500000 + i * 100 for i in range(1, 13)]  # 12 municípios, todos SP


def _cand(ano: int, sq: int) -> Candidatura:
    return Candidatura(ano, sq, f"p{sq}", f"C{sq}", "SP", DF, 14, "MISSAO", "APTO", None)


def _repo(com_ano_2022: bool = True) -> RepositorioMemoria:
    dados = DadosMemoria(
        candidaturas=[_cand(2022, 1), _cand(2026, 2)],
        municipios=[Municipio(m, m, f"M{m}", "SP", None) for m in MUNICIPIOS],
    )
    for i, m in enumerate(MUNICIPIOS, start=1):
        for ano, sq, fator in ((2022, 1, 30), (2026, 2, 60)):
            dados.eleitorado.append(EleitoradoMemoria(ano, "SP", DF, m, 1, 20000, 15000))
            dados.votos.append(VotoMemoria(ano, sq, m, 1, i * fator))
    anos = [2022, 2026] if com_ano_2022 else [2026]
    return RepositorioMemoria("2026-10-06", anos, ["SP"], [DF], dados)


@pytest.fixture
def catalogo(tmp_path: Path) -> Catalogo:
    arq = tmp_path / "g.yaml"
    arq.write_text(
        "grupos:\n"
        "  p14_2022: {rotulo: A, ano: 2022, criterio: {partido: 14}}\n"
        "  p14_2026: {rotulo: B, ano: 2026, criterio: {partido: 14}}\n"
        "comparacoes:\n"
        "  evo: {rotulo: E, de: p14_2022, para: p14_2026}\n"
    )
    return carregar_catalogo(arq, tmp_path)


def _mapa(
    repo: RepositorioMemoria,
    catalogo: Catalogo,
    ano: int,
    grupo: str | None,
    comparacao: str | None = None,
) -> Mapa:
    return montar_mapa(
        repo,
        catalogo,
        ano=ano,
        cargo=DF,
        uf="SP",
        nivel=Nivel.MUNICIPIO,
        indicador=Indicador.PENETRACAO,
        grupo_id=grupo,
        sq_candidato=None,
        comparacao=comparacao,
    )


def test_mapa_com_comparacao_usa_quebras_comuns_aos_dois_anos(catalogo: Catalogo) -> None:
    repo = _repo()
    m22 = _mapa(repo, catalogo, 2022, "p14_2022", comparacao="evo")
    m26 = _mapa(repo, catalogo, 2026, "p14_2026", comparacao="evo")
    assert m22.escala_sugerida.quebras == m26.escala_sugerida.quebras
    assert m22.escala_sugerida.quebras
    assert m22.escala_sugerida.anos == [2022, 2026]
    # a escala de 2026 sozinha seria outra (valores 2× maiores)
    sozinho = _mapa(repo, catalogo, 2026, "p14_2026")
    assert sozinho.escala_sugerida.anos == [2026]
    assert sozinho.escala_sugerida.quebras != m26.escala_sugerida.quebras


def test_comparativo_traz_a_mesma_escala_do_mapa(catalogo: Catalogo) -> None:
    repo = _repo()
    comp = montar_comparativo(
        repo,
        catalogo,
        comparacao_id="evo",
        cargo=Cargo.DEPUTADO_FEDERAL,
        uf="SP",
        mesmos_candidatos=False,
    )
    m26 = _mapa(repo, catalogo, 2026, "p14_2026", comparacao="evo")
    assert comp.escala_sugerida == m26.escala_sugerida


def test_poucos_dados_explicita_aviso_em_vez_de_quebras_inventadas(catalogo: Catalogo) -> None:
    repo = _repo()
    m = _mapa(repo, catalogo, 2026, "p14_2026", comparacao=None)
    assert m.escala_sugerida.quebras is not None  # 12 municípios ≥ 2k
    pequeno = RepositorioMemoria(
        "x",
        [2026],
        ["SP"],
        [DF],
        DadosMemoria(
            candidaturas=[_cand(2026, 2)],
            municipios=[Municipio(3500100, 3500100, "A", "SP", None)],
            eleitorado=[EleitoradoMemoria(2026, "SP", DF, 3500100, 1, 20000, 15000)],
            votos=[VotoMemoria(2026, 2, 3500100, 1, 500)],
        ),
    )
    p = _mapa(pequeno, catalogo, 2026, "p14_2026", comparacao=None)
    assert p.escala_sugerida.quebras is None
    assert p.escala_sugerida.aviso


def test_comparacao_exige_grupo_de_um_dos_lados(catalogo: Catalogo) -> None:
    from api.erros import ErroDominio

    with pytest.raises(ErroDominio):
        _mapa(_repo(), catalogo, 2026, None, comparacao="evo")


def test_n_candidaturas_conta_as_sem_situacao_publicada(catalogo: Catalogo) -> None:
    """2026 real chega com `ds_situacao_candidatura` nulo: contar zero seria dado falso (T-B15)."""
    repo = _repo()
    sem_situacao = Candidatura(2026, 2, "p2", "C2", "SP", DF, 14, "MISSAO", None, None)
    repo._d.candidaturas[:] = [_cand(2022, 1), sem_situacao]
    comp = montar_comparativo(
        repo,
        catalogo,
        comparacao_id="evo",
        cargo=Cargo.DEPUTADO_FEDERAL,
        uf="SP",
        mesmos_candidatos=False,
    )
    assert comp.n_de == 1
    assert comp.n_para == 1  # T-B15: sem situação publicada ainda conta
