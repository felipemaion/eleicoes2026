"""Serviços de domínio sobre o RepositorioMemoria (sem I/O): prova a inversão de dependência."""

import pytest
from api.dominio import Indicador, Nivel
from api.erros import ErroDominio
from api.repositorio.base import Repositorio
from api.repositorio.memoria import (
    DadosMemoria,
    EleitoradoMemoria,
    RepositorioMemoria,
    VotoMemoria,
)
from api.repositorio.modelos import Candidatura, DespesaBruta, Municipio, ReceitaBruta, VariacaoIpca
from api.servicos.candidatos import listar_candidatos, montar_ficha
from api.servicos.contas import contas_de
from api.servicos.gastos import montar_gastos
from api.servicos.grupos import Catalogo, Comparacao, DefinicaoGrupo
from api.servicos.mapa import montar_mapa

DF = "DEPUTADO FEDERAL"


def _cand(ano: int, sq: int, partido: int = 14) -> Candidatura:
    return Candidatura(ano, sq, f"p{sq}", f"N{sq}", "SP", DF, partido, "X", "APTO", None)


def _repo() -> RepositorioMemoria:
    dados = DadosMemoria(
        candidaturas=[_cand(2026, 1), _cand(2026, 2), _cand(2026, 3, partido=15), _cand(2022, 9)],
        municipios=[Municipio(10, 10, "A", "SP", 100.0), Municipio(20, 20, "B", "SP", 0.0)],
        votos=[VotoMemoria(2026, 1, 10, 1, 60), VotoMemoria(2026, 2, 10, 2, 40)],
        eleitorado=[
            EleitoradoMemoria(2026, "SP", DF, 10, 1, 500, 300),
            EleitoradoMemoria(2026, "SP", DF, 10, 2, 500, 300),
            EleitoradoMemoria(2026, "SP", DF, 20, 1, 0, 0),
        ],
        receitas={
            1: [
                ReceitaBruta(
                    1, "FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO", 10.0
                )
            ]
        },
        despesas={1: [DespesaBruta(1, "Serviços", 20.0, 5.0)]},
        ipca=[VariacaoIpca("2026-09", 0.5)],
    )
    return RepositorioMemoria("dt", [2022, 2026], ["SP"], [DF], dados, {2026: "PARCIAL"})


def _catalogo() -> Catalogo:
    g = DefinicaoGrupo(id="g", rotulo="G", ano=2026, partido=14, sqs=frozenset())
    return Catalogo({"g": g}, {"c": Comparacao(id="c", rotulo="C", de="g", para="g")})


def test_memoria_satisfaz_o_protocolo_completo() -> None:
    repo: Repositorio = _repo()
    assert repo.tp_prestacao_contas(2026) == "PARCIAL"
    assert repo.tp_prestacao_contas(2022) == "FINAL"


def test_listar_candidatos_ordena_por_votos_e_calcula_taxas() -> None:
    lista = listar_candidatos(
        _repo(), _catalogo(), grupo_id="g", uf=None, cargo=None, limite=10, offset=0
    )
    assert [i.sq_candidato for i in lista.itens] == [1, 2]
    assert lista.itens[0].penetracao == pytest.approx(60 * 1000 / 1000)
    assert lista.itens[0].pct_validos == pytest.approx(100 * 60 / 600)


def test_mapa_municipio_sem_aptos_e_null_nao_zero_nem_inf() -> None:
    mapa = montar_mapa(
        _repo(),
        _catalogo(),
        ano=2026,
        cargo=DF,
        uf="SP",
        nivel=Nivel.MUNICIPIO,
        indicador=Indicador.PENETRACAO,
        grupo_id="g",
        sq_candidato=None,
    )
    assert mapa.valores["10"] == pytest.approx(100.0)
    assert mapa.valores["20"] is None  # aptos = 0 → sem dado (spec §0)


def test_mapa_sq_de_outro_cargo_ou_inexistente() -> None:
    kw = {"ano": 2026, "uf": "SP", "nivel": Nivel.MUNICIPIO, "indicador": Indicador.VOTOS}
    with pytest.raises(ErroDominio) as e404:
        montar_mapa(_repo(), _catalogo(), cargo=DF, grupo_id=None, sq_candidato=999, **kw)  # type: ignore[arg-type]
    assert e404.value.status == 404
    with pytest.raises(ErroDominio) as e422:
        montar_mapa(
            _repo(),
            _catalogo(),
            cargo="GOVERNADOR",
            grupo_id=None,
            sq_candidato=1,
            **kw,  # type: ignore[arg-type]
        )
    assert e422.value.codigo == "candidato_fora_do_recorte"


def test_gastos_sem_votos_ficam_fora_da_razao_do_grupo() -> None:
    gastos = montar_gastos(_repo(), _catalogo(), grupo_id="g", uf=None, cargo=None)
    assert gastos.agregado.custo_voto_contratado == pytest.approx(20.0 / 60)
    assert gastos.contas_parciais is True
    assert gastos.base_ipca is None  # 2026 é nominal


def test_ipca_ausente_para_2022_falha_alto() -> None:
    from api.repositorio.base import DadosIndisponiveis

    with pytest.raises(DadosIndisponiveis, match="IPCA ausente"):
        contas_de(_repo(), 2022, [_cand(2022, 9)])


def test_ficha_inexistente_levanta_404() -> None:
    with pytest.raises(ErroDominio) as e:
        montar_ficha(_repo(), _catalogo(), 2026, 999, 10)
    assert e.value.status == 404
