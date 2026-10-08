"""Base comum das redes sociais: carrega os dados do recorte e roda os indicadores (T-A10).

Nenhuma fórmula aqui: `indicadores.redes` calcula tudo; este módulo só monta as tabelas que ele
espera e devolve o resultado em estruturas simples.

Um mesmo `username` pode ser declarado por duas candidaturas (registro duplicado da mesma
pessoa; `docs/fontes-de-dados.md`). Os indicadores identificam a conta pelo `username`, então
cada par (candidatura, perfil) entra com a chave ``"<sq>/<username>"`` — e o `media_id` dos posts
ganha o mesmo prefixo, para a deduplicação por post não fundir os dois candidatos.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

import polars as pl
from indicadores import redes as ind

from api.erros import ErroDominio, parametro_invalido
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura, PostRede, RedeDeclarada, RedesMeta, SnapshotPerfil
from api.servicos.grupos import Catalogo, candidaturas_do_grupo

ANO_REDES = 2026  # a coleta começa em 01/01/2026 (indicadores.redes.INICIO_COLETA)
STATUS_NAO_COLETADO: Final = "nao_coletado"
INSTAGRAM = "https://www.instagram.com"

_PERFIS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "sq_candidato": pl.Int64,
    "username": pl.Utf8,
    "status": pl.Utf8,
    "followers_count": pl.Int64,
    "follows_count": pl.Int64,
    "media_count": pl.Int64,
    "coletado_em": pl.Datetime("us"),
}
_POSTS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "username": pl.Utf8,
    "media_id": pl.Utf8,
    "timestamp": pl.Datetime("us"),
    "media_type": pl.Utf8,
    "like_count": pl.Int64,
    "comments_count": pl.Int64,
    "coletado_em": pl.Datetime("us"),
}
_VOTOS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "sq_candidato": pl.Int64,
    "cd_cargo": pl.Utf8,  # o agrupador de `indicadores.redes`; aqui vai o `ds_cargo`
    "votos": pl.Int64,
    "sg_uf": pl.Utf8,
}


def link_instagram(username: str) -> str:
    """Endereço público do perfil (`username` já normalizado pelo ETL: `[a-z0-9._]`)."""
    return f"{INSTAGRAM}/{username}/"


def em_utc(instante: datetime) -> datetime:
    """Instante com fuso UTC (o banco devolve datas sem fuso, que são UTC)."""
    return instante if instante.tzinfo else instante.replace(tzinfo=UTC)


def exigir_redes(repo: Repositorio) -> RedesMeta:
    """Procedência das redes; dado não publicado → 503 explícito, nunca lista vazia."""
    meta = repo.redes_meta()
    if meta is None:
        raise ErroDominio(
            503,
            "redes_indisponiveis",
            "dados de redes sociais ainda não publicados neste servidor",
        )
    return meta


def chave_conta(sq: int, username: str) -> str:
    """Chave da conta dentro de uma candidatura (ver docstring do módulo)."""
    return f"{sq}/{username}"


def username_da_chave(chave: str) -> str:
    """Inverso de `chave_conta`."""
    return chave.split("/", 1)[1]


@dataclass
class BaseRedes:
    """Dados do recorte e resultados dos indicadores, prontos para virar resposta."""

    ano: int
    meta: RedesMeta
    candidaturas: list[Candidatura]
    declaradas: dict[int, list[RedeDeclarada]]
    ultimo: dict[tuple[int, str], SnapshotPerfil]  # (sq, username) → coleta mais recente
    votos: dict[int, int]
    resumo: pl.DataFrame  # indicadores_candidato + sg_uf + resíduo, uma linha por sq
    janelas: dict[str, list[dict[str, object]]] = field(default_factory=dict)  # por chave de conta

    def __post_init__(self) -> None:
        self._por_sq: dict[int, dict[str, object]] = {
            int(str(r["sq_candidato"])): r for r in self.resumo.iter_rows(named=True)
        }

    def linha(self, sq: int) -> dict[str, object]:
        """Resumo de uma candidatura (dicionário de `indicadores_candidato` + resíduo)."""
        return self._por_sq[sq]


def _tabela_perfis(snapshots: list[SnapshotPerfil]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            (
                s.sq_candidato,
                chave_conta(s.sq_candidato, s.username),
                s.status,
                s.seguidores,
                s.seguindo,
                s.n_midias,
                s.coletado_em,
            )
            for s in snapshots
        ],
        schema=_PERFIS_SCHEMA,
        orient="row",
    )


def _tabela_posts(snapshots: list[SnapshotPerfil], posts: list[PostRede]) -> pl.DataFrame:
    por_username: dict[str, list[PostRede]] = {}
    for p in posts:
        por_username.setdefault(p.username, []).append(p)
    linhas = []
    for sq, username in sorted({(s.sq_candidato, s.username) for s in snapshots}):
        chave = chave_conta(sq, username)
        linhas += [
            (
                chave,
                f"{chave}/{p.media_id}",
                p.timestamp,
                p.media_type,
                p.curtidas,
                p.comentarios,
                p.coletado_em,
            )
            for p in por_username.get(username, [])
        ]
    return pl.DataFrame(linhas, schema=_POSTS_SCHEMA, orient="row")


def _tabela_votos(candidaturas: list[Candidatura], votos: dict[int, int]) -> pl.DataFrame:
    return pl.DataFrame(
        [(c.sq_candidato, c.ds_cargo, votos.get(c.sq_candidato), c.sg_uf) for c in candidaturas],
        schema=_VOTOS_SCHEMA,
        orient="row",
    )


def carregar(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    grupo_id: str,
    uf: str | None,
    cargo: str | None,
    agrupar_por: tuple[str, ...] = ("cd_cargo",),
) -> BaseRedes:
    """Dados do recorte do grupo + indicadores. `agrupar_por` define o ajuste log-log.

    Falha com 503 sem dado de redes e com 422 se o grupo não é de 2026 (a coleta é de 2026).
    """
    meta = exigir_redes(repo)
    grupo = catalogo.grupo(grupo_id)
    if grupo.ano != ANO_REDES:
        raise parametro_invalido(
            "redes_ano_sem_dados",
            f"redes sociais só existem para {ANO_REDES}; o grupo '{grupo_id}' é de {grupo.ano}",
        )
    candidaturas = candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo)
    return montar_base(repo, meta, candidaturas, agrupar_por)


def montar_base(
    repo: Repositorio,
    meta: RedesMeta,
    candidaturas: list[Candidatura],
    agrupar_por: tuple[str, ...] = ("cd_cargo",),
) -> BaseRedes:
    """Lê perfis, posts e votos das candidaturas (todas do mesmo ano) e roda os indicadores."""
    ano = candidaturas[0].ano if candidaturas else ANO_REDES
    sqs = [c.sq_candidato for c in candidaturas]
    declaradas: dict[int, list[RedeDeclarada]] = {}
    for d in repo.redes_declaradas(ano, sqs):
        declaradas.setdefault(d.sq_candidato, []).append(d)
    snapshots = repo.redes_perfis(ano, sqs=sqs)
    posts = repo.redes_posts(sorted({s.username for s in snapshots}))
    votos = repo.votos_totais(ano, sqs)

    perfis_df = _tabela_perfis(snapshots)
    posts_df = _tabela_posts(snapshots, posts)
    votos_df = _tabela_votos(candidaturas, votos)
    resumo = ind.indicadores_candidato(perfis_df, posts_df, votos_df.drop("sg_uf"))
    resumo = resumo.join(votos_df.select("sq_candidato", "sg_uf"), on="sq_candidato", how="left")
    ajuste = ind.residuo_log(resumo, "seguidores", "votos", por=agrupar_por)
    resumo = resumo.join(
        ajuste.drop(*[c for c in agrupar_por if c in ajuste.columns]), on="sq_candidato", how="left"
    )

    janelas: dict[str, list[dict[str, object]]] = {}
    if perfis_df.height:
        for linha in ind.metricas_janelas(perfis_df, posts_df).iter_rows(named=True):
            janelas.setdefault(str(linha["username"]), []).append(linha)
    return BaseRedes(
        ano=ano,
        meta=meta,
        candidaturas=candidaturas,
        declaradas=declaradas,
        ultimo={(s.sq_candidato, s.username): s for s in snapshots},  # ordenado: o último vence
        votos=votos,
        resumo=resumo,
        janelas=janelas,
    )
