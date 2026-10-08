"""Casos de uso /redes/correlacoes e /redes/serie.

Correlação de Spearman com IC bootstrap e ajuste log-log vêm de `indicadores.redes` (spec §9.5 e
§9.6). Aqui só se escolhem os pares, se agrupa por cargo (ou cargo × UF) e se monta a resposta.
Associação, não causalidade: o aviso acompanha toda resposta.
"""

from datetime import datetime

import polars as pl
from indicadores import redes as ind
from pydantic import BaseModel, Field

from api.erros import nao_encontrado, parametro_invalido
from api.fontes import FonteRede, fontes_redes
from api.repositorio.base import Repositorio
from api.repositorio.modelos import SnapshotPerfil
from api.servicos.grupos import Catalogo
from api.servicos.redes_base import (
    ANO_REDES,
    BaseRedes,
    carregar,
    em_utc,
    exigir_redes,
    link_instagram,
    username_da_chave,
)

AVISO_NAO_CAUSALIDADE = "redes_nao_causalidade"  # ids em docs/metodologia/publico/textos.json
AVISO_SEM_HISTORICO = "redes_seguidores_sem_historico"
# (id, rótulo, coluna x): o y é sempre `votos` (spec §9.5)
PARES = (
    ("seguidores_votos", "Seguidores × votos", "seguidores"),
    ("engajamento_votos", "Engajamento mediano na campanha × votos", "engajamento_mediano"),
    ("ritmo_votos", "Posts por semana na campanha × votos", "posts_semana_campanha"),
)


class ParCorrelacao(BaseModel):
    """ρ de Spearman entre duas medidas dos candidatos de um recorte."""

    id: str
    rotulo: str
    x: str = Field(description="Coluna do eixo x; o eixo y é sempre `votos`.")
    y: str
    n: int = Field(description="Candidatos com os dois valores.")
    n_excluidos: int = Field(description="Candidatos do recorte sem um dos valores.")
    rho: float | None = Field(description="null com menos de `n_minimo` candidatos.")
    ic_inf: float | None
    ic_sup: float | None
    n_bootstrap_validos: int | None
    nivel_ic: float
    n_minimo: int


class AjusteLogLog(BaseModel):
    """Reta `log10(1+votos) = intercepto + inclinacao · log10(1+seguidores)` (spec §9.6)."""

    intercepto: float
    inclinacao: float = Field(description="Elasticidade: +1 % de seguidores ↔ +b % de votos.")
    n: int


class PontoDispersao(BaseModel):
    """Um candidato na nuvem seguidores × votos."""

    sq_candidato: int
    nm_urna: str
    sg_uf: str
    username: str = Field(description="Conta analisada.")
    seguidores: int
    votos: int
    razao_obs_esperado: float | None = Field(description="Voto observado ÷ esperado (§9.6).")
    foto_url: str | None
    link: str = Field(description="Perfil no Instagram.")


class RecorteCorrelacao(BaseModel):
    """Correlações de um cargo (ou cargo × UF)."""

    cargo: str
    uf: str | None = Field(description="null quando o recorte soma todas as UFs do cargo.")
    n_candidatos: int
    pares: list[ParCorrelacao]
    ajuste: AjusteLogLog | None = Field(description="null com menos de 10 candidatos.")
    pontos: list[PontoDispersao]


class Correlacoes(BaseModel):
    """Corpo de GET /redes/correlacoes."""

    grupo: str
    ano: int
    cargo: str | None
    uf: str | None
    por_uf: bool
    recortes: list[RecorteCorrelacao]
    coletado_em: datetime
    avisos: list[str] = Field(description="Ids em `docs/metodologia/publico/textos.json`.")
    dt_geracao: str
    fontes: list[FonteRede]


def _recorte(
    base: BaseRedes,
    linhas: pl.DataFrame,
    correlacoes: dict[str, pl.DataFrame],
    chave: dict[str, object],
    fotos: frozenset[tuple[int, int]],
) -> RecorteCorrelacao:
    por_sq = {c.sq_candidato: c for c in base.candidaturas}
    pares = []
    for id_, rotulo, x in PARES:
        t = correlacoes[id_]
        for k, v in chave.items():
            t = t.filter(pl.col(k) == v)
        r = t.row(0, named=True)
        pares.append(
            ParCorrelacao(
                id=id_, rotulo=rotulo, x=x, y="votos", nivel_ic=ind.NIVEL,
                n_minimo=ind.N_MINIMO_CORRELACAO,
                **{k: r[k] for k in ("n", "n_excluidos", "rho", "ic_inf", "ic_sup",
                                     "n_bootstrap_validos")},
            )
        )  # fmt: skip
    com_par = linhas.filter(pl.col("seguidores").is_not_null() & pl.col("votos").is_not_null())
    pontos = [
        PontoDispersao(
            sq_candidato=int(r["sq_candidato"]),
            nm_urna=por_sq[int(r["sq_candidato"])].nm_urna,
            sg_uf=str(r["sg_uf"]),
            username=username_da_chave(str(r["username"])),
            seguidores=r["seguidores"],
            votos=r["votos"],
            razao_obs_esperado=r["razao_obs_esperado"],
            foto_url=(
                f"/fotos/{base.ano}/{r['sq_candidato']}.webp"
                if (base.ano, int(r["sq_candidato"])) in fotos
                else None
            ),
            link=link_instagram(username_da_chave(str(r["username"]))),
        )
        for r in com_par.sort("votos", descending=True).iter_rows(named=True)
    ]
    inclinacao = linhas["inclinacao"][0]
    ajuste = (
        AjusteLogLog(intercepto=linhas["intercepto"][0], inclinacao=inclinacao, n=com_par.height)
        if inclinacao is not None
        else None
    )
    return RecorteCorrelacao(
        cargo=str(linhas["cd_cargo"][0]),
        uf=str(linhas["sg_uf"][0]) if "sg_uf" in chave else None,
        n_candidatos=linhas.height,
        pares=pares,
        ajuste=ajuste,
        pontos=pontos,
    )


def montar_correlacoes(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    grupo_id: str,
    uf: str | None,
    cargo: str | None,
    por_uf: bool,
) -> Correlacoes:
    """Spearman (com IC e n) dos três pares e nuvem de pontos, por cargo (ou cargo × UF)."""
    por = ("cd_cargo", "sg_uf") if por_uf else ("cd_cargo",)
    base = carregar(repo, catalogo, grupo_id=grupo_id, uf=uf, cargo=cargo, agrupar_por=por)
    correlacoes = {id_: ind.correlacao(base.resumo, x, "votos", por=por) for id_, _, x in PARES}
    fotos = repo.fotos()
    recortes = [
        _recorte(
            base,
            base.resumo.filter(*[pl.col(k) == v for k, v in chave.items()]),
            correlacoes,
            chave,
            fotos,
        )
        for chave in correlacoes["seguidores_votos"].select(list(por)).iter_rows(named=True)
    ]
    return Correlacoes(
        grupo=grupo_id,
        ano=base.ano,
        cargo=cargo,
        uf=uf,
        por_uf=por_uf,
        recortes=recortes,
        coletado_em=em_utc(base.meta.coletado_em),
        avisos=[AVISO_NAO_CAUSALIDADE],
        dt_geracao=repo.dt_geracao(),
        fontes=fontes_redes(
            ano=base.ano, dt_geracao_tse=base.meta.dt_geracao_tse, coletado_em=base.meta.coletado_em
        ),
    )


# --- série de seguidores --------------------------------------------------------------------


class PontoSerie(BaseModel):
    """Seguidores numa coleta e variação desde a coleta válida anterior."""

    coletado_em: datetime
    seguidores: int
    delta_abs: int | None = Field(description="null no primeiro ponto.")
    delta_pct: float | None
    dias: float | None = Field(description="Dias desde a coleta anterior.")


class ResumoSerie(BaseModel):
    """Do primeiro ao último ponto; variações nulas com um só ponto."""

    n_snapshots: int
    seguidores_inicial: int
    seguidores_final: int
    delta_abs: int | None
    delta_pct: float | None
    dias: float | None


class SerieConta(BaseModel):
    """Série de seguidores de um perfil."""

    username: str
    link: str
    status: str = Field(description="Situação na coleta mais recente (`ok`, `nao_encontrado`…).")
    pontos: list[PontoSerie] = Field(description="Só coletas com seguidores; pelo menos uma.")
    resumo: ResumoSerie


class SerieRedes(BaseModel):
    """Corpo de GET /redes/serie."""

    sq_candidato: int | None
    nm_urna: str | None
    series: list[SerieConta]
    primeira_coleta: datetime = Field(description="A série não existe antes disto.")
    coletado_em: datetime
    avisos: list[str]
    dt_geracao: str
    fontes: list[FonteRede]


def _snapshots(
    repo: Repositorio, sq: int | None, username: str | None
) -> tuple[list[SnapshotPerfil], int | None, str | None]:
    """Snapshots do alvo; `username` compartilhado por duas candidaturas conta uma vez."""
    if sq is not None:
        candidatura = repo.candidatura(ANO_REDES, sq)
        if candidatura is None:
            raise nao_encontrado("candidato_nao_encontrado", f"candidato {ANO_REDES}/{sq}")
        return repo.redes_perfis(ANO_REDES, sqs=[sq]), sq, candidatura.nm_urna
    assert username is not None  # noqa: S101 - garantido por `montar_serie`
    unicos = {
        (s.username, s.coletado_em): s
        for s in reversed(repo.redes_perfis(ANO_REDES, usernames=[username]))
    }
    return sorted(unicos.values(), key=lambda s: s.coletado_em), None, None


def montar_serie(repo: Repositorio, *, sq: int | None, username: str | None) -> SerieRedes:
    """Série de seguidores por perfil, só com as coletas que existem (pelo menos uma)."""
    meta = exigir_redes(repo)
    if (sq is None) == (username is None):
        raise parametro_invalido("alvo_ambiguo", "informe exatamente um entre 'sq' e 'username'")
    snapshots, sq_resp, nome = _snapshots(repo, sq, username)
    tabela = pl.DataFrame(
        [(s.sq_candidato, s.username, s.status, s.seguidores, s.coletado_em) for s in snapshots],
        schema={
            "sq_candidato": pl.Int64, "username": pl.Utf8, "status": pl.Utf8,
            "followers_count": pl.Int64, "coletado_em": pl.Datetime("us"),
        },
        orient="row",
    )  # fmt: skip
    pontos = ind.serie_seguidores(tabela)
    resumos = {r["username"]: r for r in ind.resumo_serie_seguidores(tabela).iter_rows(named=True)}
    ultimo_status = {s.username: s.status for s in snapshots}  # ordenado: o último vence
    series = []
    for nome_conta in sorted(resumos):
        linhas = pontos.filter(pl.col("username") == nome_conta)
        r = resumos[nome_conta]
        series.append(
            SerieConta(
                username=nome_conta,
                link=link_instagram(nome_conta),
                status=ultimo_status[nome_conta],
                pontos=[
                    PontoSerie(
                        coletado_em=em_utc(p["coletado_em"]), seguidores=p["seguidores"],
                        delta_abs=p["delta_abs"], delta_pct=p["delta_pct"], dias=p["dias"],
                    )
                    for p in linhas.iter_rows(named=True)
                ],
                resumo=ResumoSerie(**{k: r[k] for k in ("n_snapshots", "seguidores_inicial",
                                                        "seguidores_final", "delta_abs",
                                                        "delta_pct", "dias")}),
            )
        )  # fmt: skip
    if not series:
        raise nao_encontrado(
            "redes_sem_serie", "nenhum perfil com seguidores coletados para esse alvo"
        )
    primeira = min(p.coletado_em for s in series for p in s.pontos)
    return SerieRedes(
        sq_candidato=sq_resp,
        nm_urna=nome,
        series=series,
        primeira_coleta=primeira,
        coletado_em=em_utc(meta.coletado_em),
        avisos=[AVISO_SEM_HISTORICO],
        dt_geracao=repo.dt_geracao(),
        fontes=fontes_redes(
            ano=ANO_REDES, dt_geracao_tse=meta.dt_geracao_tse, coletado_em=meta.coletado_em
        ),
    )
