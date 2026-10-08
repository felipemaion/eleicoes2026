"""Indicadores de desempenho (spec §2): votos nominais, % válidos, penetração, legenda, QE.

Fluxo típico para um cargo × UF × turno:

    votos = votos_nominais(votacao_candidato_munzona)            # zona → município
    tabela = indicadores_municipais(votos.rename(...), eleitorado) # candidato × município
    uf = totais_uf(tabela)

`entidade` é a coluna que identifica quem recebe votos: `sq_candidato` ou, para um grupo
tratado como candidato coletivo (`grupos.agregar_grupo`), `grupo`.
"""

from collections.abc import Sequence

import polars as pl

from indicadores._comum import (
    LIMIAR_N_BAIXO,
    exigir_colunas,
    exigir_unicidade,
    expr_pct_validos,
    expr_penetracao,
    razao,
    sobre,
)
from indicadores.espacial import lq, n_baixo

DESTINACOES_VALIDAS = ("Válido",)
DESTINACOES_ANULADAS = ("Anulado", "Anulado sub judice")
DESTINACOES_LEGENDA = ("Válido (legenda)",)
"""`NM_TIPO_DESTINACAO_VOTOS` conhecidos. Valor fora destas listas falha (spec §7 obs. c)."""


def votos_nominais(
    votacao: pl.DataFrame, chaves: Sequence[str] = ("sq_candidato", "cd_mun_ibge")
) -> pl.DataFrame:
    """Votos nominais por candidato e município, somando zonas e voto em trânsito (spec §2.1).

    `votos_nominais_validos = Σ qt_votos_nominais_validos` nas linhas de destinação "Válido";
    `votos_anulados` (destinação "Anulado"/"Anulado sub judice") e `votos_convertidos_legenda`
    ("Válido (legenda)", CE art. 175 §4º) somam `qt_votos_nominais` e ficam à parte — nunca
    entram nos votos do candidato.

    Args:
        votacao: linhas de `votacao_candidato_munzona` com `chaves`,
            `nm_tipo_destinacao_votos`, `qt_votos_nominais`, `qt_votos_nominais_validos`.
        chaves: nível de agregação (padrão candidato × município).

    Raises:
        ValueError: coluna ausente ou destinação desconhecida.
    """
    exigir_colunas(
        votacao,
        [*chaves, "nm_tipo_destinacao_votos", "qt_votos_nominais", "qt_votos_nominais_validos"],
        "votos_nominais",
    )
    conhecidas = {*DESTINACOES_VALIDAS, *DESTINACOES_ANULADAS, *DESTINACOES_LEGENDA}
    presentes = set(votacao["nm_tipo_destinacao_votos"].unique().to_list())
    if desconhecidas := presentes - conhecidas:
        raise ValueError(
            f"nm_tipo_destinacao_votos desconhecida: {sorted(map(repr, desconhecidas))}"
        )
    destino = pl.col("nm_tipo_destinacao_votos")
    return (
        votacao.group_by(list(chaves))
        .agg(
            pl.col("qt_votos_nominais_validos")
            .filter(destino.is_in(DESTINACOES_VALIDAS))
            .sum()
            .alias("votos_nominais_validos"),
            pl.col("qt_votos_nominais")
            .filter(destino.is_in(DESTINACOES_ANULADAS))
            .sum()
            .alias("votos_anulados"),
            pl.col("qt_votos_nominais")
            .filter(destino.is_in(DESTINACOES_LEGENDA))
            .sum()
            .alias("votos_convertidos_legenda"),
        )
        .sort(list(chaves))
    )


def montar_tabela(
    votos: pl.DataFrame,
    eleitorado: pl.DataFrame,
    entidade: str = "sq_candidato",
    unidade: Sequence[str] = ("cd_mun_ibge",),
) -> pl.DataFrame:
    """Tabela completa entidade × unidade com `votos`, `aptos` e `validos` (zeros explícitos).

    O TSE só traz linha onde o candidato teve voto; LQ, G e EB precisam de todas as unidades
    da UF, então a tabela é o produto entidade × unidade com `votos = 0` onde faltar linha.

    Args:
        votos: `entidade`, `unidade…`, `votos` (já agregados: uma linha por par).
        eleitorado: `unidade…`, `aptos`, `validos` do mesmo cargo e turno (uma linha por
            unidade; todas as unidades do recorte, inclusive sem voto).

    Raises:
        ValueError: coluna ausente, linha duplicada, unidade com voto e sem eleitorado,
            ou votos maiores que os válidos da unidade (dado inconsistente).
    """
    unidade = list(unidade)
    exigir_colunas(votos, [entidade, *unidade, "votos"], "montar_tabela(votos)")
    exigir_colunas(eleitorado, [*unidade, "aptos", "validos"], "montar_tabela(eleitorado)")
    exigir_unicidade(votos, [entidade, *unidade], "montar_tabela(votos)")
    exigir_unicidade(eleitorado, unidade, "montar_tabela(eleitorado)")
    orfas = votos.join(eleitorado, on=unidade, how="anti")
    if orfas.height:
        raise ValueError(f"montar_tabela: {orfas.height} linhas de votos sem eleitorado")
    tabela = (
        votos.select(entidade)
        .unique()
        .join(eleitorado.select(*unidade, "aptos", "validos"), how="cross")
        .join(votos.select(entidade, *unidade, "votos"), on=[entidade, *unidade], how="left")
        .with_columns(pl.col("votos").fill_null(0))
    )
    excesso = tabela.filter(pl.col("votos") > pl.col("validos"))
    if excesso.height:
        raise ValueError(f"montar_tabela: {excesso.height} linhas com votos maiores que os válidos")
    return tabela


def pct_validos(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `pct_validos = 100 × votos / validos` (spec §2.2); `validos = 0` → `null`.

    `validos` é `QT_TOTAL_VOTOS_VALIDOS` do mesmo cargo, turno e recorte (nominais + legenda;
    no senado com 2 vagas já soma os dois votos).
    """
    return df.with_columns(expr_pct_validos().alias("pct_validos"))


def penetracao(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `penetracao = 1000 × votos / aptos` em ‰ (spec §2.3, métrica-âncora).

    `aptos = 0` → `null`.
    """
    return df.with_columns(expr_penetracao().alias("penetracao"))


def indicadores_municipais(
    votos: pl.DataFrame,
    eleitorado: pl.DataFrame,
    entidade: str = "sq_candidato",
    unidade: Sequence[str] = ("cd_mun_ibge",),
) -> pl.DataFrame:
    """Tabela entidade × unidade com todos os indicadores por unidade de uma vez.

    Colunas: `votos, aptos, validos, pct_validos, penetracao, lq, taxa_referencia, esperado,
    n_baixo`. `taxa_referencia` é a penetração (proporção) da entidade no recorte inteiro
    (a UF), base do critério de n baixo (spec §1.4). LQ conforme spec §3.1.
    Ver `montar_tabela` para entradas e erros.
    """
    tabela = montar_tabela(votos, eleitorado, entidade, unidade)
    tabela = penetracao(pct_validos(tabela))
    tabela = tabela.with_columns(
        razao(
            sobre(pl.col("votos").sum(), [entidade]), sobre(pl.col("aptos").sum(), [entidade])
        ).alias("taxa_referencia")
    )
    return n_baixo(lq(tabela, entidade))


def totais_uf(tabela: pl.DataFrame, entidade: str = "sq_candidato") -> pl.DataFrame:
    """Soma votos, aptos e válidos por entidade sobre todas as unidades e recalcula as taxas.

    Taxa agregada = Σvotos / Σdenominador (nunca média de taxas). Recebe a saída de
    `montar_tabela`/`indicadores_municipais`.
    """
    exigir_colunas(tabela, [entidade, "votos", "aptos", "validos"], "totais_uf")
    somas = (
        tabela.group_by(entidade)
        .agg(pl.col("votos").sum(), pl.col("aptos").sum(), pl.col("validos").sum())
        .sort(entidade)
    )
    return penetracao(pct_validos(somas))


def quociente_eleitoral(validos: int, vagas: int) -> int:
    """Quociente eleitoral (CE art. 106): `validos / vagas`, fração ≤ 0,5 desprezada, > 0,5 sobe.

    Aritmética inteira para não depender de arredondamento de ponto flutuante.

    Raises:
        ValueError: `vagas ≤ 0` ou `validos < 0`.
    """
    if vagas <= 0 or validos < 0:
        raise ValueError(f"quociente eleitoral indefinido (validos={validos}, vagas={vagas})")
    inteiro, resto = divmod(validos, vagas)
    return inteiro + (1 if 2 * resto > vagas else 0)


def _qe_expr(validos: pl.Expr, vagas: pl.Expr) -> pl.Expr:
    return validos // vagas + pl.when(2 * (validos % vagas) > vagas).then(1).otherwise(0)


def votacao_partido(partidos: pl.DataFrame) -> pl.DataFrame:
    """Legenda total, votação do partido, QE, votação em QE e quociente partidário (spec §2.4).

    `votos_legenda_total = qt_votos_legenda_validos + qt_votos_nom_convr_leg_validos` (série do
    partido, nunca repartida entre candidatos); `votacao_partido = votos_nominais_validos +
    votos_legenda_total`; `quociente_eleitoral` (CE art. 106); `votacao_em_qe =
    votacao_partido / QE`; `quociente_partidario = ⌊votacao_partido / QE⌋` (CE art. 107).
    QE = 0 → `votacao_em_qe` e `quociente_partidario` nulos.

    Federação: passe uma linha por federação com as somas dos partidos (QE/QP são dela).

    Args:
        partidos: uma linha por partido (ou federação) × UF com as colunas acima mais
            `qt_total_votos_validos_uf` e `vagas`.
    """
    exigir_colunas(
        partidos,
        [
            "qt_votos_legenda_validos",
            "qt_votos_nom_convr_leg_validos",
            "votos_nominais_validos",
            "qt_total_votos_validos_uf",
            "vagas",
        ],
        "votacao_partido",
    )
    if partidos.filter(pl.col("vagas") <= 0).height:
        raise ValueError("votacao_partido: quociente eleitoral indefinido (vagas ≤ 0)")
    qe = pl.col("quociente_eleitoral")
    return (
        partidos.with_columns(
            (pl.col("qt_votos_legenda_validos") + pl.col("qt_votos_nom_convr_leg_validos")).alias(
                "votos_legenda_total"
            ),
            _qe_expr(pl.col("qt_total_votos_validos_uf"), pl.col("vagas")).alias(
                "quociente_eleitoral"
            ),
        )
        .with_columns(
            (pl.col("votos_nominais_validos") + pl.col("votos_legenda_total")).alias(
                "votacao_partido"
            )
        )
        .with_columns(
            razao(pl.col("votacao_partido"), qe).alias("votacao_em_qe"),
            pl.when(qe > 0)
            .then(pl.col("votacao_partido") // qe)
            .otherwise(None)
            .alias("quociente_partidario"),
        )
    )


def votos_km2(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `votos_km2 = votos / area_km2` (spec §2.5; só contexto). Área 0 → `null`."""
    exigir_colunas(df, ["votos", "area_km2"], "votos_km2")
    return df.with_columns(razao(pl.col("votos"), pl.col("area_km2")).alias("votos_km2"))


__all__ = [
    "LIMIAR_N_BAIXO",
    "indicadores_municipais",
    "montar_tabela",
    "pct_validos",
    "penetracao",
    "quociente_eleitoral",
    "totais_uf",
    "votacao_partido",
    "votos_km2",
    "votos_nominais",
]
