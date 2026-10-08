"""Catálogo de grupos e comparações (config/grupos.yaml) e seleção de candidaturas."""

import csv
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from api.erros import parametro_invalido
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura


class DefinicaoGrupo(BaseModel):
    """Grupo resolvido: critério por partido OU lista de `sq_candidato` (união)."""

    model_config = ConfigDict(frozen=True)

    id: str
    rotulo: str
    ano: int
    partido: int | None
    sqs: frozenset[int]


class Comparacao(BaseModel):
    """Par de grupos comparável (de → para)."""

    model_config = ConfigDict(frozen=True)

    id: str
    rotulo: str
    de: str
    para: str


class Catalogo:
    """Grupos e comparações carregados uma vez no lifespan (somente leitura depois)."""

    def __init__(
        self, grupos: Mapping[str, DefinicaoGrupo], comparacoes: Mapping[str, Comparacao]
    ) -> None:
        self.grupos = dict(grupos)
        self.comparacoes = dict(comparacoes)

    def grupo(self, grupo_id: str) -> DefinicaoGrupo:
        """Grupo pelo id; desconhecido → 422 (parâmetro inválido, não recurso ausente)."""
        if grupo_id not in self.grupos:
            raise parametro_invalido("grupo_desconhecido", f"grupo '{grupo_id}' não existe")
        return self.grupos[grupo_id]

    def comparacao(self, comparacao_id: str) -> Comparacao:
        """Comparação pelo id; desconhecida → 422."""
        if comparacao_id not in self.comparacoes:
            raise parametro_invalido(
                "comparacao_desconhecida", f"comparação '{comparacao_id}' não existe"
            )
        return self.comparacoes[comparacao_id]


def _sqs_da_lista(raiz: Path, lista: Mapping[str, object]) -> frozenset[int]:
    arquivo = raiz / str(lista["arquivo"])
    coluna = str(lista["coluna"])
    filtro = lista.get("filtro") or {}
    assert isinstance(filtro, dict)  # noqa: S101 - formato do YAML, falha alto se mudar
    sqs: set[int] = set()
    with arquivo.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            if any(linha[k] != str(v) for k, v in filtro.items()):
                continue
            if linha[coluna].strip():  # sem candidatura naquele ano = célula vazia
                sqs.add(int(linha[coluna]))
    return frozenset(sqs)


def carregar_catalogo(arquivo: Path, raiz: Path) -> Catalogo:
    """Lê grupos e comparações; CSV de lista é relativo a `raiz`. Arquivo ausente falha alto."""
    bruto = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    grupos = {}
    for gid, g in bruto["grupos"].items():
        criterio = g["criterio"]
        lista = criterio.get("lista")
        grupos[gid] = DefinicaoGrupo(
            id=gid,
            rotulo=g["rotulo"],
            ano=g["ano"],
            partido=criterio.get("partido"),
            sqs=_sqs_da_lista(raiz, lista) if lista else frozenset(),
        )
    comparacoes = {
        cid: Comparacao(id=cid, rotulo=c["rotulo"], de=c["de"], para=c["para"])
        for cid, c in (bruto.get("comparacoes") or {}).items()
    }
    return Catalogo(grupos, comparacoes)


def candidaturas_do_grupo(
    repo: Repositorio, grupo: DefinicaoGrupo, *, uf: str | None = None, cargo: str | None = None
) -> list[Candidatura]:
    """Candidaturas do grupo no ano dele. `uf` inclui as de abrangência nacional (`BR`)."""
    achadas = repo.candidaturas(
        grupo.ano, cargo=cargo, partido=grupo.partido, sqs=sorted(grupo.sqs)
    )
    return [c for c in achadas if uf is None or c.sg_uf in (uf, "BR")]


class GrupoResumo(BaseModel):
    """Item de GET /grupos."""

    id: str
    rotulo: str
    ano: int
    n_candidaturas: int = Field(description="Candidaturas do grupo presentes nos dados.")


class ComparacaoResumo(BaseModel):
    """Comparação configurada entre dois grupos."""

    id: str
    rotulo: str
    de: str
    para: str


class GruposResposta(BaseModel):
    """Corpo de GET /grupos."""

    grupos: list[GrupoResumo]
    comparacoes: list[ComparacaoResumo]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grupos": [
                        {
                            "id": "missao_2026",
                            "rotulo": "Partido Missão 2026",
                            "ano": 2026,
                            "n_candidaturas": 3,
                        }
                    ],
                    "comparacoes": [
                        {
                            "id": "evolucao_mbl",
                            "rotulo": "MBL 2022 → MBL 2026",
                            "de": "mbl_2022",
                            "para": "mbl_2026",
                        }
                    ],
                }
            ]
        }
    )


def listar_grupos(repo: Repositorio, catalogo: Catalogo) -> GruposResposta:
    """Grupos com a contagem real de candidaturas e as comparações configuradas."""
    return GruposResposta(
        grupos=[
            GrupoResumo(
                id=g.id,
                rotulo=g.rotulo,
                ano=g.ano,
                n_candidaturas=len(candidaturas_do_grupo(repo, g)),
            )
            for g in catalogo.grupos.values()
        ],
        comparacoes=[
            ComparacaoResumo(id=c.id, rotulo=c.rotulo, de=c.de, para=c.para)
            for c in catalogo.comparacoes.values()
        ],
    )
