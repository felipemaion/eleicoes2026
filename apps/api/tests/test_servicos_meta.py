"""Serviço de meta testado com o repositório em memória (sem I/O)."""

from api.repositorio.base import Repositorio
from api.repositorio.memoria import RepositorioMemoria
from api.servicos.meta import Grupo, montar_meta


def test_memoria_satisfaz_o_protocolo() -> None:
    repo: Repositorio = RepositorioMemoria(
        dt_geracao="d", anos=[2026], ufs=["SP"], cargos=["PREFEITO"]
    )
    assert repo.dt_geracao() == "d"


def test_montar_meta_ordena_e_inclui_grupos() -> None:
    repo = RepositorioMemoria(
        dt_geracao="d", anos=[2026, 2022], ufs=["SP", "RJ"], cargos=["B", "A"]
    )
    meta = montar_meta(repo, [Grupo(id="g", rotulo="G", ano=2026)])
    assert meta.anos == [2022, 2026]
    assert meta.ufs == ["RJ", "SP"]
    assert meta.cargos == ["A", "B"]
    assert meta.grupos[0].id == "g"
    assert meta.dt_geracao == "d"
