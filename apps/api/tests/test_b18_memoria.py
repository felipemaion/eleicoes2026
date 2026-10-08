"""T-B18: serviço de redes sobre o RepositorioMemoria (sem I/O) — casos que a fixture não cobre."""

from datetime import datetime

import pytest
from api.erros import ErroDominio
from api.repositorio.memoria import DadosMemoria, RepositorioMemoria, VotoMemoria
from api.repositorio.modelos import (
    Candidatura,
    PostRede,
    RedeDeclarada,
    RedesMeta,
    SnapshotPerfil,
)
from api.servicos.grupos import Catalogo, Comparacao, DefinicaoGrupo
from api.servicos.redes import montar_redes
from api.servicos.redes_correlacoes import montar_correlacoes, montar_serie
from api.servicos.redes_perfis import bloco_ficha

DF = "DEPUTADO FEDERAL"
COLETA = datetime(2026, 10, 8, 12)


def _cand(ano: int, sq: int) -> Candidatura:
    return Candidatura(ano, sq, f"p{sq}", f"N{sq}", "SP", DF, 14, "X", "APTO", None)


def _snap(sq: int, user: str, seguidores: int | None, status: str = "ok") -> SnapshotPerfil:
    return SnapshotPerfil(sq, user, status, seguidores, 1, 1, COLETA)


def _repo(com_redes: bool = True) -> RepositorioMemoria:
    declaradas = [
        RedeDeclarada(1, "um", "u1", 1, True),  # tem números, mas nenhum voto registrado
        RedeDeclarada(3, "tres", "u3", 1, True),  # perfil indisponível
        RedeDeclarada(4, "quatro", "u4", 1, True),  # tem números e votos
    ]  # sq 2 não declarou Instagram
    dados = DadosMemoria(
        candidaturas=[_cand(2026, sq) for sq in (1, 2, 3, 4)] + [_cand(2022, 9)],
        votos=[VotoMemoria(2026, 3, 10, 1, 5), VotoMemoria(2026, 4, 10, 1, 50)],
        redes_declaradas=[(2026, d) for d in declaradas],
        redes_snapshots=[
            (2026, _snap(1, "um", 100)),
            (2026, _snap(3, "tres", None, "nao_comercial")),
            (2026, _snap(4, "quatro", 500)),
        ],
        redes_posts=[PostRede("quatro", "m1", datetime(2026, 9, 1, 15), "IMAGE", 5, 1, COLETA)],
        redes_meta=RedesMeta(COLETA, "2026-10-06") if com_redes else None,
    )
    return RepositorioMemoria("dt", [2022, 2026], ["SP"], [DF], dados)


def _catalogo() -> Catalogo:
    g = DefinicaoGrupo(id="g", rotulo="G", ano=2026, partido=14, sqs=frozenset())
    return Catalogo({"g": g}, {"c": Comparacao(id="c", rotulo="C", de="g", para="g")})


def test_cada_candidato_cai_em_um_unico_motivo_de_exclusao() -> None:
    corpo = montar_redes(_repo(), _catalogo(), grupo_id="g", uf=None, cargo=None)
    assert corpo.excluidos.model_dump() == {
        "sem_instagram": 1,  # sq 2
        "nao_coletado": 0,
        "indisponivel": 1,  # sq 3
        "sem_votos": 1,  # sq 1
    }
    por_sq = {c.sq_candidato: c for c in corpo.candidatos}
    assert por_sq[1].votos is None
    assert por_sq[1].votos_por_mil_seguidores is None  # sem voto: razão nula, não zero
    assert por_sq[1].tem_dados is True
    assert por_sq[2].status == "sem_rede"
    assert por_sq[4].votos_por_mil_seguidores == pytest.approx(1000 * 50 / 500)
    assert [c.sq_candidato for c in corpo.candidatos] == [4, 3, 1, 2]  # sem voto vai para o fim


def test_candidato_sem_voto_fica_fora_da_correlacao_mas_e_contado() -> None:
    corpo = montar_correlacoes(
        _repo(), _catalogo(), grupo_id="g", uf=None, cargo=None, por_uf=False
    )
    (recorte,) = corpo.recortes
    par = recorte.pares[0]
    assert par.n == 1  # só o sq 4 tem seguidores e votos
    assert par.n_excluidos == 3
    assert par.rho is None


def test_sem_redes_publicadas_o_servico_falha_alto() -> None:
    repo = _repo(com_redes=False)
    for chamada in (
        lambda: montar_redes(repo, _catalogo(), grupo_id="g", uf=None, cargo=None),
        lambda: montar_correlacoes(
            repo, _catalogo(), grupo_id="g", uf=None, cargo=None, por_uf=False
        ),
        lambda: montar_serie(repo, sq=1, username=None),
    ):
        with pytest.raises(ErroDominio) as erro:
            chamada()
        assert erro.value.status == 503
        assert erro.value.codigo == "redes_indisponiveis"


def test_ficha_so_tem_bloco_para_2026_com_redes() -> None:
    assert bloco_ficha(_repo(), _cand(2022, 9)) is None
    assert bloco_ficha(_repo(com_redes=False), _cand(2026, 1)) is None
    bloco = bloco_ficha(_repo(), _cand(2026, 4))
    assert bloco is not None
    assert [p.username for p in bloco.perfis] == ["quatro"]
    assert bloco.perfis[0].analisado is True


def test_serie_de_conta_indisponivel_e_404() -> None:
    with pytest.raises(ErroDominio) as erro:
        montar_serie(_repo(), sq=3, username=None)
    assert erro.value.status == 404
