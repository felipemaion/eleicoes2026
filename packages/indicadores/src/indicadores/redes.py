"""Indicadores de redes sociais — Instagram (spec §9, ADR 0008).

Entradas: `redes_perfis` (um registro por coleta) e `redes_posts` do `dados` (T-D08), com datas
em UTC. Funções puras polars→polars; o bootstrap usa um gerador com semente fixa, então o
resultado é reprodutível.

Referências: Spearman (1904); Efron & Tibshirani (1993), intervalo percentil;
Gayo-Avello (2013) e DiGrazia et al. (2013) sobre redes sociais e voto.
"""

import math
import random
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from indicadores._comum import exigir_colunas, exigir_unicidade, razao, spearman_listas

__all__ = [
    "aplicar_renomeacoes",
    "conta_analisada",
    "correlacao",
    "indicadores_candidato",
    "metricas_janelas",
    "residuo_log",
    "resumo_serie_seguidores",
    "serie_seguidores",
    "spearman_listas",
    "ultimo_snapshot",
]

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")
"""As janelas usam a data em Brasília (UTC−3, sem horário de verão desde 2019; spec §9.0)."""
INICIO_COLETA = date(2026, 1, 1)
FIM_PRE_CAMPANHA = date(2026, 8, 15)
INICIO_CAMPANHA = date(2026, 8, 16)
"""Propaganda eleitoral permitida a partir de 16/08 (Lei 9.504/1997, art. 36)."""
PRIMEIRO_TURNO = date(2026, 10, 4)
INICIO_POS_ELEICAO = date(2026, 10, 5)
JANELAS = ("pre_campanha", "campanha", "pos_eleicao", "total")
DIAS_MINIMOS_TAXA = 7.0
"""Janela mais curta que isto não tem taxa semanal (três dias não estimam um ritmo; §9.0)."""
IDADE_MINIMA_ENGAJAMENTO = timedelta(hours=48)
"""Post mais novo que isto na coleta ainda acumula curtidas: fica fora do engajamento (§9.2)."""
N_MINIMO_CORRELACAO = 10
N_BOOTSTRAP = 2000
SEMENTE = 2026
NIVEL = 0.95
STATUS_SEM_REDE = "sem_rede"

_COLUNAS_PERFIS = ("sq_candidato", "username", "status", "followers_count", "coletado_em")
_COLUNAS_POSTS = (
    "username",
    "media_id",
    "timestamp",
    "media_type",
    "like_count",
    "comments_count",
    "coletado_em",
)
_US_POR_DIA = 86_400 * 1_000_000


def _inicio_utc(dia: date) -> datetime:
    """00:00 de `dia` em Brasília, expresso em UTC."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=FUSO_BRASILIA).astimezone(UTC)


def _em_utc(df: pl.DataFrame, colunas: Sequence[str]) -> pl.DataFrame:
    """Datas em `Datetime(us, UTC)`. Sem fuso = UTC (é o que o contrato do `dados` promete)."""
    exprs = []
    for c in colunas:
        tipo = df.schema[c]
        if not isinstance(tipo, pl.Datetime):
            raise ValueError(f"redes: coluna {c} deveria ser data/hora, é {tipo}")
        e = pl.col(c).dt.cast_time_unit("us")
        e = (
            e.dt.replace_time_zone("UTC")
            if tipo.time_zone is None
            else e.dt.convert_time_zone("UTC")
        )
        exprs.append(e)
    return df.with_columns(exprs)


def _dias(fim: pl.Expr, inicio: datetime) -> pl.Expr:
    return (fim - pl.lit(inicio)).dt.total_microseconds() / _US_POR_DIA


def ultimo_snapshot(perfis: pl.DataFrame) -> pl.DataFrame:
    """Último registro de cada conta (`username`), com ou sem métricas.

    Falha alto em snapshot repetido (mesma conta e mesmo `coletado_em`).
    """
    return (
        _snapshots(perfis, "redes.ultimo_snapshot")
        .group_by("username", maintain_order=True)
        .last()
        .sort("username")
    )


def aplicar_renomeacoes(df: pl.DataFrame, renomeacoes: pl.DataFrame | None) -> pl.DataFrame:
    """Troca `username` pela identidade atual da conta (mapa `username_tse → username_atual`).

    Ponto de extensão para contas renomeadas (T-D15): os snapshots sob o nome declarado ao TSE e
    sob o nome atual passam a ser **uma série só** (spec §9.0, conta analisada). Vale para
    `redes_perfis` e `redes_posts`; aplique às duas antes dos demais indicadores. Sem mapa
    (`None`), devolve `df` intacto. Falha alto em `username_tse` repetido ou mapa encadeado
    (a→b e b→c), que deixaria a identidade ambígua.
    """
    if renomeacoes is None:
        return df
    exigir_colunas(renomeacoes, ("username_tse", "username_atual"), "redes.aplicar_renomeacoes")
    exigir_colunas(df, ("username",), "redes.aplicar_renomeacoes")
    mapa = renomeacoes.filter(pl.col("username_tse") != pl.col("username_atual"))
    repetidos = mapa.filter(pl.col("username_tse").is_duplicated())["username_tse"].unique()
    if repetidos.len():
        raise ValueError(f"redes.aplicar_renomeacoes: username_tse repetido: {repetidos.to_list()}")
    encadeados = set(mapa["username_tse"].to_list()) & set(mapa["username_atual"].to_list())
    if encadeados:
        raise ValueError(f"redes.aplicar_renomeacoes: renomeação encadeada: {sorted(encadeados)}")
    de_para = dict(
        zip(mapa["username_tse"].to_list(), mapa["username_atual"].to_list(), strict=True)
    )
    return df.with_columns(pl.col("username").replace(de_para))


def _snapshots(perfis: pl.DataFrame, contexto: str) -> pl.DataFrame:
    exigir_colunas(perfis, _COLUNAS_PERFIS, contexto)
    exigir_unicidade(perfis, ("username", "coletado_em"), contexto)
    return _em_utc(perfis, ["coletado_em"]).sort("coletado_em")


def _ultimo_valido(snapshots: pl.DataFrame, chave: Sequence[str]) -> pl.DataFrame:
    """Último snapshot com seguidores de cada `chave` (contas sem nenhum válido ficam fora)."""
    return (
        snapshots.filter(pl.col("followers_count").is_not_null())
        .group_by(chave, maintain_order=True)
        .last()
    )


def conta_analisada(perfis: pl.DataFrame) -> pl.DataFrame:
    """Conta analisada de cada candidato e a situação dela na coleta (spec §9.0, T-A13).

    Conta analisada = a de **mais seguidores em qualquer snapshot válido** da série (máximo
    histórico; empate: `username`). Uma falha de coleta nunca troca a conta: se o snapshot mais
    recente dela não é válido, os números vêm do **último válido dela**, com
    `conta_indisponivel_desde` (primeira coleta falha depois dele) e `desatualizado = true`.
    Sem nenhum snapshot válido: a conta de menor `username` só como link, `seguidores` nulo.
    Colunas: `sq_candidato, username, status` (do último válido; senão o da coleta mais recente),
    `status_ultima_coleta, seguidores, seguindo, ultima_coleta_ok, conta_indisponivel_desde,
    desatualizado`. Contas renomeadas: aplique `aplicar_renomeacoes` antes.
    """
    snaps = _snapshots(perfis, "redes.conta_analisada")
    chave = ["sq_candidato", "username"]
    validos = snaps.filter(pl.col("followers_count").is_not_null())
    com_dados = (
        validos.group_by(chave)
        .agg(pl.col("followers_count").max().alias("_maximo"))
        .sort(["sq_candidato", "_maximo", "username"], descending=[False, True, False])
        .unique(subset="sq_candidato", keep="first", maintain_order=True)
        .select(chave)
    )
    sem_dados = (
        snaps.join(com_dados.select("sq_candidato"), on="sq_candidato", how="anti")
        .group_by("sq_candidato")
        .agg(pl.col("username").min())
    )
    escolhidas = pl.concat([com_dados, sem_dados.select(chave)])
    seguindo = (
        pl.col("follows_count") if "follows_count" in snaps.columns else pl.lit(None, pl.Int64)
    )
    ultimo_ok = _ultimo_valido(snaps, chave).select(
        *chave,
        pl.col("status").alias("_status_ok"),
        pl.col("followers_count").alias("seguidores"),
        seguindo.alias("seguindo"),
        pl.col("coletado_em").alias("ultima_coleta_ok"),
    )
    ultimo = snaps.group_by(chave).agg(pl.col("status").last().alias("status_ultima_coleta"))
    falhas = (
        snaps.join(ultimo_ok.select(*chave, "ultima_coleta_ok"), on=chave, how="inner")
        .filter(pl.col("coletado_em") > pl.col("ultima_coleta_ok"))
        .group_by(chave)
        .agg(pl.col("coletado_em").min().alias("conta_indisponivel_desde"))
    )
    return (
        escolhidas.join(ultimo_ok, on=chave, how="left")
        .join(ultimo, on=chave, how="left")
        .join(falhas, on=chave, how="left")
        .with_columns(
            pl.coalesce("_status_ok", "status_ultima_coleta").alias("status"),
            pl.col("conta_indisponivel_desde").is_not_null().alias("desatualizado"),
        )
        .sort("sq_candidato")
        .select(
            *chave,
            "status",
            "status_ultima_coleta",
            "seguidores",
            "seguindo",
            "ultima_coleta_ok",
            "conta_indisponivel_desde",
            "desatualizado",
        )
    )


def _posts_unicos(posts: pl.DataFrame) -> pl.DataFrame:
    """Um registro por `media_id`: o da coleta mais recente (curtidas acumuladas; §9.0)."""
    exigir_colunas(posts, _COLUNAS_POSTS, "redes.posts")
    return (
        _em_utc(posts, ["timestamp", "coletado_em"])
        .sort("coletado_em")
        .unique(subset="media_id", keep="last", maintain_order=True)
    )


def _filtro_janela(janela: str, dia: pl.Expr) -> pl.Expr:
    if janela == "pre_campanha":
        return dia.is_between(INICIO_COLETA, FIM_PRE_CAMPANHA)
    if janela == "campanha":
        return dia.is_between(INICIO_CAMPANHA, PRIMEIRO_TURNO)
    if janela == "pos_eleicao":
        return dia >= INICIO_POS_ELEICAO
    return dia >= INICIO_COLETA


def _dias_janela(janela: str) -> pl.Expr:
    if janela == "pre_campanha":
        return pl.lit(float((FIM_PRE_CAMPANHA - INICIO_COLETA).days + 1))
    if janela == "campanha":
        return pl.lit(float((PRIMEIRO_TURNO - INICIO_CAMPANHA).days + 1))
    inicio = INICIO_POS_ELEICAO if janela == "pos_eleicao" else INICIO_COLETA
    return _dias(pl.col("fim"), _inicio_utc(inicio))


def _por_semana(n: str) -> pl.Expr:
    return (
        pl.when(pl.col("dias") >= DIAS_MINIMOS_TAXA)
        .then(7 * razao(pl.col(n), pl.col("dias")))
        .otherwise(pl.lit(None, dtype=pl.Float64))
    )


def metricas_janelas(perfis: pl.DataFrame, posts: pl.DataFrame) -> pl.DataFrame:
    """Posts, vídeos, ritmo semanal e engajamento por conta × janela (spec §9.1 e §9.2).

    Só contas com algum snapshot válido; seguidores e fim das janelas abertas vêm do **último
    snapshot válido** (uma coleta falha não apaga as métricas; T-A13). Janelas: `pre_campanha`,
    `campanha`, `pos_eleicao` (até a última coleta válida da conta) e `total`. Taxa por semana nula
    em janela com menos de 7 dias; `pct_video` nulo sem post. Engajamento por post =
    `100 × (curtidas + comentários) / seguidores`, sem curtidas/comentários nulos nem posts com
    menos de 48 h na coleta; média, mediana e `n_posts_engajamento`.
    """
    contas = (
        _ultimo_valido(_snapshots(perfis, "redes.metricas_janelas"), ["username"])
        .sort("username")
        .select(
            "username",
            pl.col("followers_count").alias("seguidores"),
            pl.col("coletado_em").alias("fim"),
        )
    )
    unicos = _posts_unicos(posts).join(contas, on="username", how="inner")
    idade = pl.col("coletado_em") - pl.col("timestamp")
    unicos = unicos.with_columns(
        pl.col("timestamp").dt.convert_time_zone(FUSO_BRASILIA.key).dt.date().alias("dia"),
        pl.when(idade >= IDADE_MINIMA_ENGAJAMENTO)
        .then(100 * razao(pl.col("like_count") + pl.col("comments_count"), pl.col("seguidores")))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("engajamento"),
    )
    grade = pl.concat(
        [
            contas.with_columns(
                pl.lit(j).alias("janela"), pl.lit(i).alias("_ordem"), _dias_janela(j).alias("dias")
            )
            for i, j in enumerate(JANELAS)
        ]
    )
    contagens = pl.concat(
        [
            unicos.filter(_filtro_janela(j, pl.col("dia")))
            .group_by("username")
            .agg(
                pl.len().cast(pl.Int64).alias("n_posts"),
                (pl.col("media_type") == "VIDEO").sum().cast(pl.Int64).alias("n_videos"),
                pl.col("engajamento").count().cast(pl.Int64).alias("n_posts_engajamento"),
                pl.col("engajamento").mean().alias("engajamento_medio"),
                pl.col("engajamento").median().alias("engajamento_mediano"),
            )
            .with_columns(pl.lit(j).alias("janela"))
            for j in JANELAS
        ],
        how="vertical_relaxed",
    )
    return (
        grade.join(contagens, on=["username", "janela"], how="left")
        .with_columns(pl.col("n_posts", "n_videos", "n_posts_engajamento").fill_null(0))
        .with_columns(
            _por_semana("n_posts").alias("posts_por_semana"),
            _por_semana("n_videos").alias("videos_por_semana"),
            (100 * razao(pl.col("n_videos"), pl.col("n_posts"))).alias("pct_video"),
        )
        .sort("username", "_ordem")
        .select(
            "username",
            "janela",
            "dias",
            "n_posts",
            "n_videos",
            "posts_por_semana",
            "videos_por_semana",
            "pct_video",
            "n_posts_engajamento",
            pl.col("engajamento_medio").cast(pl.Float64),
            pl.col("engajamento_mediano").cast(pl.Float64),
        )
    )


def _da_janela(janelas: pl.DataFrame, janela: str, colunas: dict[str, str]) -> pl.DataFrame:
    return janelas.filter(janela=janela).select(
        "username", *[pl.col(origem).alias(destino) for origem, destino in colunas.items()]
    )


def indicadores_candidato(
    perfis: pl.DataFrame, posts: pl.DataFrame, votos: pl.DataFrame
) -> pl.DataFrame:
    """Resumo por candidatura (spec §9.3): uma linha por `sq_candidato` de `votos`.

    `votos` traz `sq_candidato, cd_cargo, votos` (nominais válidos, §2.1). Conta = a de
    `conta_analisada` (máximo histórico, sem fallback em falha de coleta, com
    `ultima_coleta_ok`, `conta_indisponivel_desde`, `desatualizado`, `status_ultima_coleta`);
    sem perfil → `status = sem_rede`. Colunas: seguidores e seguindo,
    `seguidores_por_mil_votos`, `votos_por_mil_seguidores`, ritmo de posts na campanha e no
    pós e `variacao_ritmo_pct`, `pct_video` (janela total),
    engajamento mediano e médio da campanha, `tem_dados`.
    """
    exigir_colunas(votos, ("sq_candidato", "cd_cargo", "votos"), "redes.indicadores_candidato")
    exigir_unicidade(votos, ("sq_candidato",), "redes.indicadores_candidato")
    principal = conta_analisada(perfis)
    janelas = metricas_janelas(perfis, posts)
    campanha = _da_janela(
        janelas,
        "campanha",
        {
            "posts_por_semana": "posts_semana_campanha",
            "engajamento_mediano": "engajamento_mediano",
            "engajamento_medio": "engajamento_medio",
        },
    )
    pos = _da_janela(janelas, "pos_eleicao", {"posts_por_semana": "posts_semana_pos"})
    total = _da_janela(janelas, "total", {"pct_video": "pct_video"})
    return (
        votos.select("sq_candidato", "cd_cargo", "votos")
        .join(principal, on="sq_candidato", how="left")
        .join(campanha, on="username", how="left")
        .join(pos, on="username", how="left")
        .join(total, on="username", how="left")
        .with_columns(
            pl.col("status").fill_null(STATUS_SEM_REDE),
            pl.col("seguidores").is_not_null().alias("tem_dados"),
            pl.col("desatualizado").fill_null(False),
            (1000 * razao(pl.col("seguidores"), pl.col("votos"))).alias("seguidores_por_mil_votos"),
            (1000 * razao(pl.col("votos"), pl.col("seguidores"))).alias("votos_por_mil_seguidores"),
            (100 * razao(pl.col("posts_semana_pos"), pl.col("posts_semana_campanha")) - 100).alias(
                "variacao_ritmo_pct"
            ),
        )
        .sort("sq_candidato")
        .select(
            "sq_candidato",
            "cd_cargo",
            "votos",
            "username",
            "status",
            "tem_dados",
            "status_ultima_coleta",
            "ultima_coleta_ok",
            "conta_indisponivel_desde",
            "desatualizado",
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
    )


def _snapshots_validos(perfis: pl.DataFrame) -> pl.DataFrame:
    return (
        _snapshots(perfis, "redes.serie_seguidores")
        .filter(pl.col("followers_count").is_not_null())
        .sort("username", "coletado_em")
    )


def serie_seguidores(perfis: pl.DataFrame) -> pl.DataFrame:
    """Seguidores por snapshot e variação desde o snapshot válido anterior (spec §9.4).

    Snapshot sem seguidores sai; o primeiro de cada conta tem variações nulas.
    """
    anterior = pl.col("followers_count").shift(1).over("username")
    return _snapshots_validos(perfis).select(
        "sq_candidato",
        "username",
        "coletado_em",
        pl.col("followers_count").alias("seguidores"),
        (pl.col("followers_count") - anterior).alias("delta_abs"),
        (100 * razao(pl.col("followers_count"), anterior) - 100).alias("delta_pct"),
        (
            (
                pl.col("coletado_em") - pl.col("coletado_em").shift(1).over("username")
            ).dt.total_microseconds()
            / _US_POR_DIA
        ).alias("dias"),
    )


def resumo_serie_seguidores(perfis: pl.DataFrame) -> pl.DataFrame:
    """Variação do primeiro ao último snapshot válido de cada conta; < 2 snapshots → nulas."""
    resumo = (
        _snapshots_validos(perfis)
        .group_by("username", maintain_order=True)
        .agg(
            pl.len().cast(pl.Int64).alias("n_snapshots"),
            pl.col("followers_count").first().alias("seguidores_inicial"),
            pl.col("followers_count").last().alias("seguidores_final"),
            pl.col("coletado_em").first().alias("_t0"),
            pl.col("coletado_em").last().alias("_t1"),
        )
    )
    dois = pl.col("n_snapshots") >= 2

    def _so_com_dois(e: pl.Expr) -> pl.Expr:
        return pl.when(dois).then(e).otherwise(None)

    return resumo.select(
        "username",
        "n_snapshots",
        "seguidores_inicial",
        "seguidores_final",
        _so_com_dois(pl.col("seguidores_final") - pl.col("seguidores_inicial")).alias("delta_abs"),
        _so_com_dois(
            100 * razao(pl.col("seguidores_final"), pl.col("seguidores_inicial")) - 100
        ).alias("delta_pct"),
        _so_com_dois((pl.col("_t1") - pl.col("_t0")).dt.total_microseconds() / _US_POR_DIA).alias(
            "dias"
        ),
    )


def _quantil(valores: list[float], q: float) -> float:
    """Quantil com interpolação linear (igual ao padrão do numpy)."""
    ordenados = sorted(valores)
    pos = q * (len(ordenados) - 1)
    baixo = math.floor(pos)
    alto = min(baixo + 1, len(ordenados) - 1)
    return ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (pos - baixo)


def _correlacao_grupo(
    xs: list[float], ys: list[float], n_bootstrap: int, nivel: float, semente: int, n_minimo: int
) -> dict[str, Any]:
    n = len(xs)
    vazio: dict[str, Any] = {
        "rho": None,
        "ic_inf": None,
        "ic_sup": None,
        "n_bootstrap_validos": None,
    }
    rho = spearman_listas(xs, ys) if n >= n_minimo else None
    if rho is None:
        return vazio
    rng = random.Random(semente)  # noqa: S311 - reamostragem estatística, não criptografia
    replicas = []
    for _ in range(n_bootstrap):
        idx = rng.choices(range(n), k=n)
        r = spearman_listas([xs[i] for i in idx], [ys[i] for i in idx])
        if r is not None:  # réplica com variância zero não tem ρ
            replicas.append(r)
    alfa = (1 - nivel) / 2
    return {
        "rho": rho,
        "ic_inf": _quantil(replicas, alfa),
        "ic_sup": _quantil(replicas, 1 - alfa),
        "n_bootstrap_validos": len(replicas),
    }


def correlacao(
    df: pl.DataFrame,
    x: str,
    y: str,
    *,
    por: Sequence[str] = ("cd_cargo",),
    n_bootstrap: int = N_BOOTSTRAP,
    nivel: float = NIVEL,
    semente: int = SEMENTE,
    n_minimo: int = N_MINIMO_CORRELACAO,
) -> pl.DataFrame:
    """ρ de Spearman entre `x` e `y` por grupo `por`, com IC bootstrap percentil (spec §9.5).

    Pares com nulo saem e são contados (`n_excluidos`). Com menos de `n_minimo` pares ou
    variância zero, ρ e IC são nulos. Reamostragem pareada dos candidatos, em ordem de
    `sq_candidato`, com `random.Random(semente)` novo por grupo (reprodutível).
    Associação, não causalidade.
    """
    exigir_colunas(df, (x, y, "sq_candidato", *por), "redes.correlacao")
    if not 0 < nivel < 1:
        raise ValueError(f"redes.correlacao: nivel deve estar entre 0 e 1 (recebido {nivel})")
    if n_bootstrap < 1:
        raise ValueError("redes.correlacao: n_bootstrap deve ser positivo")
    linhas = []
    for chave, grupo in (
        df.sort("sq_candidato").partition_by(list(por), as_dict=True, maintain_order=True).items()
    ):
        pares = grupo.select(x, y).drop_nulls()
        xs = [float(v) for v in pares[x].to_list()]
        ys = [float(v) for v in pares[y].to_list()]
        linhas.append(
            {
                **dict(zip(por, chave, strict=True)),
                "n": len(xs),
                "n_excluidos": grupo.height - len(xs),
                **_correlacao_grupo(xs, ys, n_bootstrap, nivel, semente, n_minimo),
            }
        )
    schema: dict[str, Any] = {c: df.schema[c] for c in por}
    schema |= {
        "n": pl.Int64,
        "n_excluidos": pl.Int64,
        "rho": pl.Float64,
        "ic_inf": pl.Float64,
        "ic_sup": pl.Float64,
        "n_bootstrap_validos": pl.Int64,
    }
    return pl.DataFrame(linhas, schema=schema).sort(list(por))


def residuo_log(
    df: pl.DataFrame,
    x: str = "seguidores",
    y: str = "votos",
    *,
    por: Sequence[str] = ("cd_cargo",),
    n_minimo: int = N_MINIMO_CORRELACAO,
) -> pl.DataFrame:
    """Ajuste `log10(1+y) = a + b·log10(1+x)` por grupo e resíduo por candidato (spec §9.6).

    Mínimos quadrados só com `x` e `y` não nulos; grupo com menos de `n_minimo` pares ou `x`
    constante → tudo nulo. `razao_obs_esperado = 10^residuo_log10` (2 = o dobro do esperado).
    """
    exigir_colunas(df, (x, y, "sq_candidato", *por), "redes.residuo_log")
    if df.select((pl.col(x) < 0) | (pl.col(y) < 0)).to_series().any():
        raise ValueError(f"redes.residuo_log: {x} e {y} não podem ser negativos")
    grupo = list(por)
    valido = pl.col(x).is_not_null() & pl.col(y).is_not_null()
    lx = pl.when(valido).then((1 + pl.col(x).cast(pl.Float64)).log10())
    ly = pl.when(valido).then((1 + pl.col(y).cast(pl.Float64)).log10())
    base = df.with_columns(lx.alias("_lx"), ly.alias("_ly"))
    mx = pl.col("_lx").mean().over(grupo)
    my = pl.col("_ly").mean().over(grupo)
    sxx = ((pl.col("_lx") - mx) ** 2).sum().over(grupo)
    sxy = ((pl.col("_lx") - mx) * (pl.col("_ly") - my)).sum().over(grupo)
    n = pl.col("_lx").count().over(grupo)
    inclinacao = pl.when((n >= n_minimo) & (sxx > 0)).then(sxy / sxx)
    ajustado = base.with_columns(inclinacao.alias("inclinacao")).with_columns(
        (my - pl.col("inclinacao") * mx).alias("intercepto")
    )
    previsto = pl.col("intercepto") + pl.col("inclinacao") * pl.col("_lx")
    return (
        ajustado.with_columns(
            (10**previsto - 1).alias("votos_esperados"),
            (pl.col("_ly") - previsto).alias("residuo_log10"),
        )
        .with_columns((10 ** pl.col("residuo_log10")).alias("razao_obs_esperado"))
        .sort([*grupo, "sq_candidato"])
        .select(
            "sq_candidato",
            *grupo,
            "intercepto",
            "inclinacao",
            "votos_esperados",
            "residuo_log10",
            "razao_obs_esperado",
        )
    )
