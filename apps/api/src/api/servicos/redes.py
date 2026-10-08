"""Caso de uso /redes: Instagram dos candidatos de um grupo, com indicadores da T-A10.

O leitor precisa distinguir situações que valem coisas diferentes e nunca viram zero:
``sem_rede`` (não declarou Instagram ao TSE), ``nao_coletado`` (declarou; a coleta ainda não
chegou), ``nao_encontrado``/``nao_comercial`` (a API da Meta não mostra números: conta pessoal
ou inexistente) e ``ok``.
"""

from datetime import datetime
from statistics import median
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from api.fontes import FonteRede, fontes_redes
from api.fotos import ComFotoELink, foto_e_link
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.candidatos import Partido
from api.servicos.grupos import Catalogo
from api.servicos.redes_base import STATUS_NAO_COLETADO, BaseRedes, carregar, em_utc
from api.servicos.redes_perfis import PerfilRede, perfis_do_candidato

StatusRede = Literal["ok", "nao_encontrado", "nao_comercial", "nao_coletado", "sem_rede"]
AVISO_CONTAS_SEM_DADOS = "redes_contas_sem_dados"  # id em docs/metodologia/publico/textos.json


class JanelaRede(BaseModel):
    """Posts e engajamento da conta analisada numa janela (spec §9.1 e §9.2)."""

    janela: Literal["pre_campanha", "campanha", "pos_eleicao", "total"]
    dias: float
    n_posts: int
    n_videos: int
    posts_por_semana: float | None = Field(description="null em janela com menos de 7 dias.")
    videos_por_semana: float | None
    pct_video: float | None = Field(description="null sem posts na janela.")
    n_posts_engajamento: int = Field(description="Posts que entram no engajamento.")
    engajamento_medio: float | None = Field(description="% dos seguidores por post (§9.2).")
    engajamento_mediano: float | None


class VotoEsperado(BaseModel):
    """Voto observado × esperado pelo tamanho da conta (ajuste log-log, spec §9.6)."""

    votos_esperados: float
    residuo_log10: float
    razao_obs_esperado: float = Field(description="2 = o dobro do esperado; 0,5 = metade.")


class RedeCandidato(ComFotoELink):
    """Candidato com seus perfis e indicadores de redes."""

    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    partido: Partido
    votos: int | None = Field(description="Votos nominais válidos; null = sem voto registrado.")
    status: StatusRede
    tem_dados: bool = Field(description="A conta analisada tem seguidores (conta com números).")
    perfis: list[PerfilRede]
    seguidores: int | None
    seguindo: int | None
    seguidores_por_mil_votos: float | None
    votos_por_mil_seguidores: float | None
    posts_semana_campanha: float | None
    posts_semana_pos: float | None
    variacao_ritmo_pct: float | None = Field(description="Pós-eleição vs. campanha (§9.1).")
    pct_video: float | None
    engajamento_mediano: float | None = Field(description="Janela da campanha.")
    engajamento_medio: float | None
    janelas: list[JanelaRede] = Field(description="Conta analisada; vazio sem números.")
    voto_esperado: VotoEsperado | None = Field(
        description="null sem números ou com menos de 10 candidatos com dados no cargo."
    )


class AgregadoRedes(BaseModel):
    """Resumo do grupo no recorte, só com as contas com números."""

    n_candidatos: int
    n_com_dados: int
    seguidores_total: int | None
    mediana_seguidores: float | None
    mediana_posts_semana_campanha: float | None
    mediana_engajamento_mediano: float | None
    mediana_pct_video: float | None


class Excluidos(BaseModel):
    """Candidatos fora das médias e correlações, por motivo (cada candidato conta uma vez)."""

    sem_instagram: int = Field(description="Não declararam Instagram ao TSE.")
    nao_coletado: int = Field(description="Declararam, mas a coleta ainda não chegou.")
    indisponivel: int = Field(description="Conta pessoal ou inexistente: a API não dá números.")
    sem_votos: int = Field(description="Têm números de rede, mas nenhum voto registrado.")


class Redes(BaseModel):
    """Corpo de GET /redes."""

    grupo: str
    ano: int
    cargo: str | None
    uf: str | None
    candidatos: list[RedeCandidato] = Field(description="Ordenados por votos (maior primeiro).")
    agregado: AgregadoRedes
    excluidos: Excluidos
    coletado_em: datetime = Field(description="Coleta mais recente do Instagram (UTC).")
    avisos: list[str] = Field(description="Ids em `docs/metodologia/publico/textos.json`.")
    dt_geracao: str
    fontes: list[FonteRede]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grupo": "missao_2026",
                    "ano": 2026,
                    "cargo": "DEPUTADO FEDERAL",
                    "uf": "SP",
                    "candidatos": [],
                    "agregado": {
                        "n_candidatos": 2,
                        "n_com_dados": 1,
                        "seguidores_total": 10500,
                        "mediana_seguidores": 10500.0,
                        "mediana_posts_semana_campanha": 0.56,
                        "mediana_engajamento_mediano": 20.95,
                        "mediana_pct_video": 33.3,
                    },
                    "excluidos": {
                        "sem_instagram": 0,
                        "nao_coletado": 0,
                        "indisponivel": 1,
                        "sem_votos": 0,
                    },
                    "coletado_em": "2026-10-08T12:00:00Z",
                    "avisos": ["redes_contas_sem_dados"],
                    "dt_geracao": "2026-10-06",
                    "fontes": [],
                }
            ]
        }
    )


def _status(base: BaseRedes, sq: int) -> StatusRede:
    """Situação do candidato: distingue 'não coletado' de 'sem Instagram' (o indicador não)."""
    coletado = any(s == sq for s, _ in base.ultimo)
    if not coletado:
        return STATUS_NAO_COLETADO if base.declaradas.get(sq) else "sem_rede"
    return cast(StatusRede, str(base.linha(sq)["status"]))


def _janelas(base: BaseRedes, sq: int) -> list[JanelaRede]:
    linha = base.linha(sq)
    if not linha["tem_dados"]:
        return []
    return [JanelaRede.model_validate(j) for j in base.janelas[str(linha["username"])]]


def _voto_esperado(linha: dict[str, object]) -> VotoEsperado | None:
    if linha.get("razao_obs_esperado") is None:
        return None
    return VotoEsperado.model_validate(
        {k: linha[k] for k in ("votos_esperados", "residuo_log10", "razao_obs_esperado")}
    )


def candidato_redes(
    base: BaseRedes, c: Candidatura, fotos: frozenset[tuple[int, int]]
) -> RedeCandidato:
    """Uma candidatura com perfis, janelas e indicadores."""
    sq = c.sq_candidato
    linha = base.linha(sq)
    resumo = {
        k: linha[k]
        for k in (
            "seguidores",
            "seguindo",
            "seguidores_por_mil_votos",
            "votos_por_mil_seguidores",
            "posts_semana_campanha",
            "posts_semana_pos",
            "variacao_ritmo_pct",
            "pct_video",
            "engajamento_mediano",
            "engajamento_medio",
        )
    }
    return RedeCandidato.model_validate(
        {
            "sq_candidato": sq,
            "nm_urna": c.nm_urna,
            "sg_uf": c.sg_uf,
            "cargo": c.ds_cargo,
            "partido": Partido(numero=c.nr_partido, sigla=c.sg_partido),
            "votos": base.votos.get(sq),
            "status": _status(base, sq),
            "tem_dados": bool(linha["tem_dados"]),
            "perfis": perfis_do_candidato(base, sq),
            "janelas": _janelas(base, sq),
            "voto_esperado": _voto_esperado(linha),
            **resumo,
            **foto_e_link(fotos, ano=base.ano, sq_candidato=sq, uf=c.sg_uf),
        }
    )


def _mediana(valores: list[float]) -> float | None:
    return float(median(valores)) if valores else None


def _agregado(candidatos: list[RedeCandidato]) -> AgregadoRedes:
    com = [c for c in candidatos if c.tem_dados]

    def valores(campo: str) -> list[float]:
        return [float(v) for c in com if (v := getattr(c, campo)) is not None]

    seguidores = valores("seguidores")
    return AgregadoRedes(
        n_candidatos=len(candidatos),
        n_com_dados=len(com),
        seguidores_total=int(sum(seguidores)) if seguidores else None,
        mediana_seguidores=_mediana(seguidores),
        mediana_posts_semana_campanha=_mediana(valores("posts_semana_campanha")),
        mediana_engajamento_mediano=_mediana(valores("engajamento_mediano")),
        mediana_pct_video=_mediana(valores("pct_video")),
    )


def _excluidos(candidatos: list[RedeCandidato]) -> Excluidos:
    return Excluidos(
        sem_instagram=sum(c.status == "sem_rede" for c in candidatos),
        nao_coletado=sum(c.status == STATUS_NAO_COLETADO for c in candidatos),
        indisponivel=sum(
            c.status in ("nao_encontrado", "nao_comercial") and not c.tem_dados for c in candidatos
        ),
        sem_votos=sum(c.tem_dados and c.votos is None for c in candidatos),
    )


def montar_redes(
    repo: Repositorio, catalogo: Catalogo, *, grupo_id: str, uf: str | None, cargo: str | None
) -> Redes:
    """Perfis e indicadores de redes do grupo no recorte (cargo × UF)."""
    base = carregar(repo, catalogo, grupo_id=grupo_id, uf=uf, cargo=cargo)
    fotos = repo.fotos()
    candidatos = sorted(
        (candidato_redes(base, c, fotos) for c in base.candidaturas),
        key=lambda c: (c.votos is None, -(c.votos or 0), c.sq_candidato),
    )
    excluidos = _excluidos(candidatos)
    return Redes(
        grupo=grupo_id,
        ano=base.ano,
        cargo=cargo,
        uf=uf,
        candidatos=candidatos,
        agregado=_agregado(candidatos),
        excluidos=excluidos,
        coletado_em=em_utc(base.meta.coletado_em),
        avisos=[AVISO_CONTAS_SEM_DADOS] if excluidos.indisponivel else [],
        dt_geracao=repo.dt_geracao(),
        fontes=fontes_redes(
            ano=base.ano, dt_geracao_tse=base.meta.dt_geracao_tse, coletado_em=base.meta.coletado_em
        ),
    )
