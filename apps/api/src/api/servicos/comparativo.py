"""Caso de uso /comparativo: evolução 2022→2026 por AMC e KPIs do grupo."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Cargo
from api.erros import parametro_invalido
from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos import adaptador_indicadores as ind
from api.servicos.grupos import Catalogo, DefinicaoGrupo, candidaturas_do_grupo


class GrupoRef(BaseModel):
    """Grupo de um dos lados da comparação."""

    id: str
    rotulo: str
    ano: int


class EvolucaoMunicipio(BaseModel):
    """Evolução numa AMC (município IBGE com desmembramentos agregados, §5.1)."""

    cd_amc: int
    nome: str
    uf: str
    penetracao_de: float | None
    penetracao_para: float | None
    delta_penetracao: float | None = Field(description="‰ — métrica-âncora.")
    swing_pp: float | None = Field(description="p.p. de votos válidos.")
    retencao: float | None = Field(description="votos_para / votos_de; null se votos_de = 0.")
    ganho_absoluto: int
    votos_de: int
    votos_para: int


class KpisComparativo(BaseModel):
    """Os mesmos indicadores sobre o recorte inteiro (Σ votos / Σ base, não média de AMCs)."""

    penetracao_de: float | None
    penetracao_para: float | None
    delta_penetracao: float | None
    swing_pp: float | None
    retencao: float | None
    ganho_absoluto: int
    votos_de: int
    votos_para: int


class Comparativo(BaseModel):
    """Corpo de GET /comparativo."""

    comparacao: str
    rotulo: str
    de: GrupoRef
    para: GrupoRef
    cargo: str
    uf: str | None
    mesmos_candidatos: bool
    n_de: int = Field(description="Candidaturas do lado 'de' (após o recorte).")
    n_para: int
    kpis: KpisComparativo
    municipios: list[EvolucaoMunicipio]
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "comparacao": "evolucao_mbl",
                    "rotulo": "MBL 2022 → MBL 2026",
                    "de": {"id": "mbl_2022", "rotulo": "MBL 2022", "ano": 2022},
                    "para": {"id": "mbl_2026", "rotulo": "MBL 2026", "ano": 2026},
                    "cargo": "DEPUTADO FEDERAL",
                    "uf": "SP",
                    "mesmos_candidatos": False,
                    "n_de": 3,
                    "n_para": 3,
                    "kpis": {
                        "penetracao_de": 70.3,
                        "penetracao_para": 107.4,
                        "delta_penetracao": 37.1,
                        "swing_pp": 5.9,
                        "retencao": 1.62,
                        "ganho_absoluto": 720,
                        "votos_de": 1160,
                        "votos_para": 1880,
                    },
                    "municipios": [],
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


def _lado(
    repo: Repositorio, grupo: DefinicaoGrupo, cargo: str, uf: str | None
) -> list[Candidatura]:
    return candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo)


def _base_municipios(
    repo: Repositorio, ano: int, cargo: str, uf: str | None, sqs: Sequence[int]
) -> list[ind.BaseMunicipio]:
    votos = {v.cd_mun_ibge: v.votos for v in repo.votos_territorio(ano, sqs, por_zona=False, uf=uf)}
    return [
        ind.BaseMunicipio(b.cd_mun_ibge, b.aptos, b.validos, votos.get(b.cd_mun_ibge, 0))
        for b in repo.base_eleitoral(ano, cargo, por_zona=False, uf=uf)
    ]


def montar_comparativo(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    comparacao_id: str,
    cargo: Cargo,
    uf: str | None,
    mesmos_candidatos: bool,
) -> Comparativo:
    """Evolução do grupo `de` para `para`; opcionalmente só as mesmas pessoas (`pessoa_id`)."""
    if cargo is Cargo.SENADOR:
        # 2022 elegeu 1 vaga (1 voto) e 2026 elege 2 (2 votos): taxas incomparáveis (§1.8).
        raise parametro_invalido(
            "cargo_sem_evolucao", "Senado não entra em evolução 2022→2026 (1 voto × 2 votos)"
        )
    comp = catalogo.comparacao(comparacao_id)
    de, para = catalogo.grupo(comp.de), catalogo.grupo(comp.para)
    c_de, c_para = _lado(repo, de, cargo.value, uf), _lado(repo, para, cargo.value, uf)
    if mesmos_candidatos:
        pessoas = {c.pessoa_id for c in c_de} & {c.pessoa_id for c in c_para}
        c_de = [c for c in c_de if c.pessoa_id in pessoas]
        c_para = [c for c in c_para if c.pessoa_id in pessoas]
    base_de = _base_municipios(repo, de.ano, cargo.value, uf, [c.sq_candidato for c in c_de])
    base_para = _base_municipios(repo, para.ano, cargo.value, uf, [c.sq_candidato for c in c_para])
    codigos = sorted({b.cd_mun_ibge for b in (*base_de, *base_para)})
    municipios = {m.cd_mun_ibge: m for m in repo.municipios(codigos)}
    try:
        evolucao = ind.evolucao({k: m.cd_amc for k, m in municipios.items()}, base_de, base_para)
    except ValueError as erro:  # município sem linha em `municipios`: dado inconsistente
        raise DadosIndisponiveis(str(erro)) from erro
    cabeca = {m.cd_mun_ibge: m for m in repo.municipios([e.amc for e in evolucao])}
    return Comparativo(
        comparacao=comp.id,
        rotulo=comp.rotulo,
        de=GrupoRef(id=de.id, rotulo=de.rotulo, ano=de.ano),
        para=GrupoRef(id=para.id, rotulo=para.rotulo, ano=para.ano),
        cargo=cargo.value,
        uf=uf,
        mesmos_candidatos=mesmos_candidatos,
        n_de=len(c_de),
        n_para=len(c_para),
        kpis=_kpis(base_de, base_para),
        municipios=[
            EvolucaoMunicipio(
                cd_amc=e.amc,
                nome=cabeca[e.amc].nome,
                uf=cabeca[e.amc].uf,
                penetracao_de=e.penetracao_2022,
                penetracao_para=e.penetracao_2026,
                delta_penetracao=e.delta_penetracao,
                swing_pp=e.swing_pp,
                retencao=e.retencao,
                ganho_absoluto=e.ganho_absoluto,
                votos_de=e.votos_2022,
                votos_para=e.votos_2026,
            )
            for e in evolucao
        ],
        dt_geracao=repo.dt_geracao(),
    )


def _kpis(
    base_de: Sequence[ind.BaseMunicipio], base_para: Sequence[ind.BaseMunicipio]
) -> KpisComparativo:
    a = (
        sum(b.aptos for b in base_de),
        sum(b.validos for b in base_de),
        sum(b.votos for b in base_de),
    )
    p = (
        sum(b.aptos for b in base_para),
        sum(b.validos for b in base_para),
        sum(b.votos for b in base_para),
    )
    pen_de, pen_para = ind.penetracao(a[2], a[0]), ind.penetracao(p[2], p[0])
    return KpisComparativo(
        penetracao_de=pen_de,
        penetracao_para=pen_para,
        delta_penetracao=ind.diferenca(pen_de, pen_para),
        swing_pp=ind.diferenca(ind.pct_validos(a[2], a[1]), ind.pct_validos(p[2], p[1])),
        retencao=p[2] / a[2] if a[2] else None,
        ganho_absoluto=p[2] - a[2],
        votos_de=a[2],
        votos_para=p[2],
    )
