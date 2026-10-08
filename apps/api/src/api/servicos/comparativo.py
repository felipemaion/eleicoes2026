"""Caso de uso /comparativo: evolução 2022→2026 por AMC e KPIs do grupo."""

from collections.abc import Sequence

import polars as pl
from indicadores import evolucao, grupos
from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Cargo
from api.erros import parametro_invalido
from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
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
    ganho_absoluto: int | None = Field(description="null se a AMC só existe num dos anos.")
    votos_de: int | None
    votos_para: int | None


class KpisComparativo(BaseModel):
    """Os mesmos indicadores sobre o recorte inteiro (Σ votos / Σ base, não média de AMCs)."""

    penetracao_de: float | None
    penetracao_para: float | None
    delta_penetracao: float | None
    swing_pp: float | None
    retencao: float | None
    ganho_absoluto: int | None
    votos_de: int | None
    votos_para: int | None


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


_ESQUEMA = {"cd_mun_ibge": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64, "votos": pl.Int64}


def _quadro(
    repo: Repositorio, ano: int, cargo: str, uf: str | None, sqs: Sequence[int]
) -> pl.DataFrame:
    """`cd_mun_ibge, aptos, validos, votos` de todos os municípios do recorte (zero explícito)."""
    votos = {v.cd_mun_ibge: v.votos for v in repo.votos_territorio(ano, sqs, por_zona=False, uf=uf)}
    return pl.DataFrame(
        [
            (b.cd_mun_ibge, b.aptos, b.validos, votos.get(b.cd_mun_ibge, 0))
            for b in repo.base_eleitoral(ano, cargo, por_zona=False, uf=uf)
        ],
        schema=_ESQUEMA,
        orient="row",
    )


def _pessoas(candidaturas: Sequence[Candidatura], votos: dict[int, int]) -> pl.DataFrame:
    return pl.DataFrame(
        [(c.pessoa_id, votos.get(c.sq_candidato, 0)) for c in candidaturas],
        schema={"pessoa_id": pl.String, "votos": pl.Int64},
        orient="row",
    )


def _n_aptas(candidaturas: Sequence[Candidatura]) -> int:
    quadro = pl.DataFrame(
        [(c.sq_candidato, c.ds_situacao_candidatura) for c in candidaturas],
        schema={"sq_candidato": pl.Int64, "ds_situacao_candidatura": pl.String},
        orient="row",
    )
    return int(grupos.n_candidatos(quadro, [c.sq_candidato for c in candidaturas]).item())


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
        v_de = repo.votos_totais(de.ano, [c.sq_candidato for c in c_de])
        v_para = repo.votos_totais(para.ano, [c.sq_candidato for c in c_para])
        comuns = set(
            evolucao.mesmos_candidatos(_pessoas(c_de, v_de), _pessoas(c_para, v_para))[
                "pessoa_ids"
            ].item()
        )
        c_de = [c for c in c_de if c.pessoa_id in comuns]
        c_para = [c for c in c_para if c.pessoa_id in comuns]
    q_de = _quadro(repo, de.ano, cargo.value, uf, [c.sq_candidato for c in c_de])
    q_para = _quadro(repo, para.ano, cargo.value, uf, [c.sq_candidato for c in c_para])
    codigos = sorted(set(q_de["cd_mun_ibge"]) | set(q_para["cd_mun_ibge"]))
    municipios = {m.cd_mun_ibge: m for m in repo.municipios(codigos)}
    crosswalk = pl.DataFrame(
        [(k, m.cd_amc) for k, m in municipios.items()],
        schema={"cd_mun_ibge": pl.Int64, "amc": pl.Int64},
        orient="row",
    )
    todos = pl.DataFrame(
        {"cd_mun_ibge": codigos, "amc": [0] * len(codigos)}, schema=crosswalk.schema
    )
    try:
        por_amc = evolucao.evolucao(q_de, q_para, crosswalk)
        # Recorte inteiro como uma AMC só: Σ votos / Σ base, não média de AMCs.
        total = evolucao.evolucao(q_de, q_para, todos)
    except ValueError as erro:  # município sem AMC: dado inconsistente
        raise DadosIndisponiveis(str(erro)) from erro
    cabecas = {m.cd_mun_ibge: m for m in repo.municipios(por_amc["amc"].to_list())}
    if any(a not in cabecas for a in por_amc["amc"]):
        raise DadosIndisponiveis("AMC sem município de referência")
    kpis = total.to_dicts()[0] if total.height else {}
    return Comparativo(
        comparacao=comp.id,
        rotulo=comp.rotulo,
        de=GrupoRef(id=de.id, rotulo=de.rotulo, ano=de.ano),
        para=GrupoRef(id=para.id, rotulo=para.rotulo, ano=para.ano),
        cargo=cargo.value,
        uf=uf,
        mesmos_candidatos=mesmos_candidatos,
        n_de=_n_aptas(c_de),
        n_para=_n_aptas(c_para),
        kpis=KpisComparativo(
            penetracao_de=kpis.get("penetracao_2022"),
            penetracao_para=kpis.get("penetracao_2026"),
            delta_penetracao=kpis.get("delta_penetracao"),
            swing_pp=kpis.get("swing_pp"),
            retencao=kpis.get("retencao"),
            ganho_absoluto=kpis.get("ganho_absoluto"),
            votos_de=kpis.get("votos_2022"),
            votos_para=kpis.get("votos_2026"),
        ),
        municipios=[
            EvolucaoMunicipio(
                cd_amc=e["amc"],
                nome=cabecas[e["amc"]].nome,
                uf=cabecas[e["amc"]].uf,
                penetracao_de=e["penetracao_2022"],
                penetracao_para=e["penetracao_2026"],
                delta_penetracao=e["delta_penetracao"],
                swing_pp=e["swing_pp"],
                retencao=e["retencao"],
                ganho_absoluto=e["ganho_absoluto"],
                votos_de=e["votos_2022"],
                votos_para=e["votos_2026"],
            )
            for e in por_amc.to_dicts()
        ],
        dt_geracao=repo.dt_geracao(),
    )
