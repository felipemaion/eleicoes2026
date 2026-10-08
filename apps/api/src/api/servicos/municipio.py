"""Caso de uso /municipios/{cd}: resumo do município para cada grupo e cargo."""

from pydantic import BaseModel, ConfigDict

from api.erros import nao_encontrado
from api.repositorio.base import Repositorio
from api.servicos import adaptador_indicadores as ind
from api.servicos.grupos import Catalogo, candidaturas_do_grupo


class ResumoCargo(BaseModel):
    """Desempenho do grupo num cargo dentro do município (um cargo por vez, spec §0)."""

    cargo: str
    n_candidaturas: int
    votos: int
    aptos: int
    penetracao: float | None
    pct_validos: float | None
    votos_por_km2: float | None


class ResumoGrupo(BaseModel):
    """Grupo e seus cargos no município."""

    id: str
    rotulo: str
    ano: int
    cargos: list[ResumoCargo]


class ResumoMunicipio(BaseModel):
    """Corpo de GET /municipios/{cd_mun_ibge}."""

    cd_mun_ibge: int
    nome: str
    uf: str
    area_km2: float | None
    grupos: list[ResumoGrupo]
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "cd_mun_ibge": 3550308,
                    "nome": "São Paulo",
                    "uf": "SP",
                    "area_km2": 1521.11,
                    "grupos": [
                        {
                            "id": "missao_2026",
                            "rotulo": "Partido Missão 2026",
                            "ano": 2026,
                            "cargos": [
                                {
                                    "cargo": "DEPUTADO FEDERAL",
                                    "n_candidaturas": 2,
                                    "votos": 1100,
                                    "aptos": 15000,
                                    "penetracao": 73.33,
                                    "pct_validos": 10.48,
                                    "votos_por_km2": 0.72,
                                }
                            ],
                        }
                    ],
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


def montar_resumo(repo: Repositorio, catalogo: Catalogo, cd_mun_ibge: int) -> ResumoMunicipio:
    """Resumo do município; inexistente → 404."""
    achados = repo.municipios([cd_mun_ibge])
    if not achados:
        raise nao_encontrado("municipio_nao_encontrado", f"município {cd_mun_ibge}")
    m = achados[0]
    grupos = []
    for grupo in catalogo.grupos.values():
        por_cargo: dict[str, list[int]] = {}
        for c in candidaturas_do_grupo(repo, grupo, uf=m.uf):
            por_cargo.setdefault(c.ds_cargo, []).append(c.sq_candidato)
        cargos = []
        for cargo, sqs in sorted(por_cargo.items()):
            base = next(
                (
                    b
                    for b in repo.base_eleitoral(grupo.ano, cargo, por_zona=False, uf=m.uf)
                    if b.cd_mun_ibge == cd_mun_ibge
                ),
                None,
            )
            if base is None:  # cargo sem eleitorado apurado no município: nada a resumir
                continue
            votos = sum(
                v.votos
                for v in repo.votos_territorio(grupo.ano, sqs, por_zona=False, uf=m.uf)
                if v.cd_mun_ibge == cd_mun_ibge
            )
            cargos.append(
                ResumoCargo(
                    cargo=cargo,
                    n_candidaturas=len(sqs),
                    votos=votos,
                    aptos=base.aptos,
                    penetracao=ind.penetracao(votos, base.aptos),
                    pct_validos=ind.pct_validos(votos, base.validos),
                    votos_por_km2=votos / m.area_km2 if m.area_km2 else None,
                )
            )
        grupos.append(ResumoGrupo(id=grupo.id, rotulo=grupo.rotulo, ano=grupo.ano, cargos=cargos))
    return ResumoMunicipio(
        cd_mun_ibge=m.cd_mun_ibge,
        nome=m.nome,
        uf=m.uf,
        area_km2=m.area_km2,
        grupos=grupos,
        dt_geracao=repo.dt_geracao(),
    )
