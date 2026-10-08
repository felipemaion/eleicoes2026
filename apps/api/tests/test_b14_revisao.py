"""T-B14, revisão: sem receita ≠ zero, nulos, denominador de aptos e comparativo nulo."""

import pytest
from api.dominio import Cargo
from api.repositorio.memoria import (
    DadosMemoria,
    EleitoradoMemoria,
    RepositorioMemoria,
    VotoMemoria,
)
from api.repositorio.modelos import Candidatura, DespesaBruta, Municipio, ReceitaBruta, VariacaoIpca
from api.servicos.comparativo import montar_comparativo
from api.servicos.contas import _receitas_out, contas_de
from api.servicos.grupos import Catalogo, Comparacao, DefinicaoGrupo
from indicadores import financeiro

DF = "DEPUTADO FEDERAL"
DE = "DEPUTADO ESTADUAL"
FEFC = ("FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO")
REPASSE = ("OUTROS RECURSOS", "Recursos de outros candidatos", "FINANCEIRO")


def _ipca() -> list[VariacaoIpca]:
    meses = [f"{a}-{m:02d}" for a in range(2022, 2027) for m in range(1, 13)]
    return [VariacaoIpca(m, 0.5) for m in meses if "2022-09" <= m <= "2026-09"]


def _cand(ano: int, sq: int, uf: str = "SP", cargo: str = DF) -> Candidatura:
    return Candidatura(ano, sq, f"p{sq}", f"N{sq}", uf, cargo, 14, "X", "APTO", None)


def _repo(
    receitas: dict[int, list[ReceitaBruta]] | None = None, **extra: object
) -> RepositorioMemoria:
    dados = DadosMemoria(
        candidaturas=[
            _cand(2026, 1),
            _cand(2026, 2),
            _cand(2026, 3),
            _cand(2026, 4),
            _cand(2026, 5, "RJ"),
            _cand(2022, 9),
            _cand(2022, 10, cargo=DE),
        ],
        municipios=[Municipio(10, 10, "A", "SP", 0.0), Municipio(20, 20, "B", "RJ", 0.0)],
        votos=[
            VotoMemoria(2026, 1, 10, 1, 60),
            VotoMemoria(2026, 2, 10, 2, 40),
            VotoMemoria(2026, 4, 10, 4, 10),
            VotoMemoria(2026, 5, 20, 1, 5),
        ],
        eleitorado=[
            EleitoradoMemoria(2026, "SP", DF, 10, 1, 800, 600),
            EleitoradoMemoria(2026, "RJ", DF, 20, 1, 200, 150),
            EleitoradoMemoria(2022, "SP", DF, 10, 1, 700, 500),
            EleitoradoMemoria(2022, "SP", DE, 10, 1, 700, 500),
        ],
        receitas=receitas
        if receitas is not None
        else {
            1: [ReceitaBruta(1, *FEFC[:2], FEFC[2], 10.0)],
            2: [ReceitaBruta(2, *FEFC[:2], FEFC[2], 30.0)],  # 0 votos nominais? não: 40
            3: [ReceitaBruta(3, *FEFC[:2], FEFC[2], 7.0)],  # sem voto algum
        },
        despesas={
            1: [DespesaBruta(1, "Serviços", 20.0, 5.0)],
            3: [DespesaBruta(3, "Serviços", 1.0, 1.0)],
            4: [DespesaBruta(4, "Serviços", 8.0, 2.0)],  # despesa SEM nenhuma receita
        },
        ipca=_ipca(),
        **extra,  # type: ignore[arg-type]
    )
    return RepositorioMemoria("dt", [2022, 2026], ["SP", "RJ"], [DF, DE], dados, {2026: "PARCIAL"})


def _contas(sqs: list[int]):  # type: ignore[no-untyped-def]
    repo = _repo()
    return contas_de(repo, 2026, [repo.candidatura(2026, sq) for sq in sqs])  # type: ignore[misc]


def test_candidato_com_despesa_e_sem_receita_nao_tem_receita_zero() -> None:
    contas = _contas([1, 2, 4])
    c4 = next(c for c in contas.por_candidato if c.candidatura.sq_candidato == 4)
    assert c4.receita_total is None
    assert c4.receita_por_voto is None
    assert c4.saldo_contratado is None
    assert c4.pct_receita_gasta is None
    # fora das estatísticas do grupo, contado como excluído
    assert contas.distribuicao.n_candidatos == 3
    assert contas.distribuicao.n_com_contas == 2
    assert contas.distribuicao.media == pytest.approx(20.0)
    assert contas.receita_por_voto.candidatos_sem_contas_excluidos == 1
    # o saldo do grupo só soma quem tem receita (a despesa do sq 4 não vira saldo negativo)
    assert contas.saldo.saldo_contratado == pytest.approx(40.0 - 20.0)


def test_sem_nenhuma_receita_a_ficha_nao_inventa_zero() -> None:
    contas = _contas([4])
    assert contas.receitas is None
    assert contas.saldo.saldo_contratado is None
    assert contas.distribuicao.media is None


def test_candidato_com_receita_e_sem_voto_tem_receita_por_voto_nula() -> None:
    contas = _contas([1, 3])
    c3 = next(c for c in contas.por_candidato if c.candidatura.sq_candidato == 3)
    assert c3.receita_por_voto is None  # votos = 0
    assert c3.receita_total == 7.0
    assert contas.receita_por_voto.candidatos_sem_voto_excluidos == 1
    assert contas.receita_por_voto.receita_por_voto == pytest.approx(10.0 / 60)


def test_repasse_sem_doador_continua_visivel_na_faixa() -> None:
    receitas = {
        1: [
            ReceitaBruta(1, *REPASSE[:2], REPASSE[2], 4.0),
            ReceitaBruta(1, *FEFC[:2], FEFC[2], 6.0),
        ]
    }
    repo = _repo(receitas)
    rec = contas_de(repo, 2026, [repo.candidatura(2026, 1)]).receitas  # type: ignore[misc,union-attr]
    assert rec is not None
    assert rec.receita_repasses_internos == 0.0
    assert rec.receita_repasses_doador_desconhecido == 4.0
    assert rec.faixa_receita is not None
    assert (rec.faixa_receita.minima, rec.faixa_receita.maxima) == (6.0, 10.0)


def test_nulo_da_lib_continua_nulo_na_saida() -> None:
    linha: dict[str, float | None] = {
        "receita_total": None, "receita_financeira": None, "receita_estimavel": None,
        "receita_repasses_candidatos": None, "receita_sem_repasses": None,
        "pct_publico": None, "pct_autofinanciamento": None, "pct_pessoa_fisica": None,
        "pct_estimavel": None, "hhi_fontes": None, "n_efetivo_fontes": None,
        **{f"receita_{c}": None for c in financeiro.CATEGORIAS_RECEITA},
    }  # fmt: skip
    out = _receitas_out(linha)
    assert out.receita_total is None
    assert out.receita_estimavel is None
    assert out.receita_repasses_candidatos is None
    assert out.receita_sem_repasses is None
    assert out.faixa_receita is None


def test_receita_por_mil_aptos_usa_o_eleitorado_de_todo_o_grupo_no_cargo() -> None:
    # sq 5 (RJ) não tem contas (2026 parcial): seu eleitorado entra no denominador mesmo assim.
    contas = _contas([1, 5])
    assert contas.aptos == 800 + 200
    assert contas.receita_por_mil_aptos == pytest.approx(1000 * 10.0 / 1000)


def test_receita_por_mil_aptos_nulo_com_varios_cargos_em_2022() -> None:
    repo = _repo(
        {
            9: [ReceitaBruta(9, *FEFC[:2], FEFC[2], 5.0)],
            10: [ReceitaBruta(10, *FEFC[:2], FEFC[2], 5.0)],
        }
    )
    contas = contas_de(repo, 2022, [repo.candidatura(2022, 9), repo.candidatura(2022, 10)])  # type: ignore[misc]
    assert contas.receita_por_mil_aptos is None
    assert contas.aptos is None


def test_soma_da_distribuicao_fecha_com_receita_total_do_grupo() -> None:
    receitas = {
        1: [ReceitaBruta(1, *FEFC[:2], FEFC[2], 10.0)],
        2: [
            ReceitaBruta(2, *REPASSE[:2], REPASSE[2], 5.0, 1),
            ReceitaBruta(2, *FEFC[:2], FEFC[2], 30.0),
        ],
    }
    repo = _repo(receitas)
    contas = contas_de(repo, 2026, [repo.candidatura(2026, 1), repo.candidatura(2026, 2)])  # type: ignore[misc]
    assert contas.receitas is not None
    assert contas.receitas.receita_repasses_internos == 5.0
    assert contas.distribuicao.soma == contas.receitas.receita_total == 40.0


def _catalogo() -> Catalogo:
    g22 = DefinicaoGrupo(id="g22", rotulo="G22", ano=2022, partido=14, sqs=frozenset())
    g26 = DefinicaoGrupo(id="g26", rotulo="G26", ano=2026, partido=14, sqs=frozenset())
    comp = {
        "c": Comparacao(id="c", rotulo="C", de="g22", para="g26"),
        "mesmo": Comparacao(id="mesmo", rotulo="M", de="g26", para="g26"),
    }
    return Catalogo({"g22": g22, "g26": g26}, comp)


def test_comparativo_sem_par_2022_2026_nao_tem_receitas() -> None:
    corpo = montar_comparativo(
        _repo(), _catalogo(), comparacao_id="mesmo", cargo=Cargo.DEPUTADO_FEDERAL, uf="SP",
        mesmos_candidatos=False,
    )  # fmt: skip
    assert corpo.receitas is None


def test_comparativo_com_lado_sem_contas_nao_tem_receitas() -> None:
    # 2022 (sq 9) não tem nenhuma receita nem despesa
    corpo = montar_comparativo(
        _repo(), _catalogo(), comparacao_id="c", cargo=Cargo.DEPUTADO_FEDERAL, uf="SP",
        mesmos_candidatos=False,
    )  # fmt: skip
    assert corpo.receitas is None
