"""Grupos como "candidato coletivo" (spec §0, §5.3; ADR 0005).

A resolução de `config/grupos.yaml` em lista de `sq_candidato` é da API; aqui só entra a
lista já resolvida. Indicador de grupo = o mesmo indicador sobre a soma dos votos dos
membros no **mesmo cargo, turno e UF** — nunca somando cargos (o eleitor vota uma vez em
cada cargo; somar dupla-contaria).
"""

from collections.abc import Sequence

import polars as pl

from indicadores._colunas import (
    CD_CARGO,
    DS_SITUACAO_CANDIDATURA,
    NR_TURNO,
)
from indicadores._comum import exigir_colunas, exigir_valor_unico
from indicadores.financeiro import expr_repasse_candidato, resumo_receitas

SITUACAO_APTA = "APTO"


def agregar_grupo(
    votos: pl.DataFrame,
    membros: Sequence[object],
    grupo: str,
    entidade: str = "sq_candidato",
    chaves: Sequence[str] = ("cd_mun_ibge",),
) -> pl.DataFrame:
    """Soma os votos dos `membros` por `chaves`, devolvendo a entidade coletiva `grupo`.

    Saída `grupo, chaves…, votos`, pronta para `desempenho.indicadores_municipais(...,
    entidade="grupo")`. Membro sem linha de voto simplesmente não soma.

    Raises:
        ValueError: lista de membros vazia, ou cargos/turnos misturados entre os membros.
    """
    if not membros:
        raise ValueError(f"agregar_grupo: grupo {grupo!r} sem membros")
    exigir_colunas(votos, [entidade, *chaves, "votos"], "agregar_grupo")
    dos_membros = votos.filter(pl.col(entidade).is_in(list(membros)))
    exigir_valor_unico(dos_membros, CD_CARGO, "um cargo por vez", "agregar_grupo")
    exigir_valor_unico(dos_membros, NR_TURNO, "um turno por vez", "agregar_grupo")
    return (
        dos_membros.group_by(list(chaves))
        .agg(pl.col("votos").sum())
        .select(pl.lit(grupo).alias("grupo"), *chaves, "votos")
    )


def n_candidatos(
    candidaturas: pl.DataFrame,
    membros: Sequence[object],
    por: Sequence[str] = (),
    entidade: str = "sq_candidato",
) -> pl.DataFrame:
    """Número de candidaturas aptas do grupo (spec §5.3): `ds_situacao_candidatura = APTO`.

    Candidatos com zero voto contam; renúncias antes da urna não. Com `por` (ex.: `sg_uf`),
    recortes sem candidatura apta não aparecem (o `n` deles é 0 → indicador por candidato nulo).
    """
    exigir_colunas(candidaturas, [entidade, *por, DS_SITUACAO_CANDIDATURA], "n_candidatos")
    aptas = candidaturas.filter(
        pl.col(entidade).is_in(list(membros)) & (pl.col(DS_SITUACAO_CANDIDATURA) == SITUACAO_APTA)
    )
    contagem = pl.len().alias("n_candidatos")
    if not por:
        return aptas.select(contagem)
    return aptas.group_by(list(por)).agg(contagem).sort(list(por))


def receitas_grupo(
    receitas: pl.DataFrame, membros: Sequence[object], entidade: str = "sq_candidato"
) -> pl.DataFrame:
    """Resumo de receitas do grupo sem os repasses internos (spec §4.6). Uma linha.

    Repasse de candidato é reconhecido pela **origem** (`financeiro.expr_repasse_candidato`),
    não pela categoria — o FEFC repassado chega com fonte FEFC. Repasse cujo doador
    (`sq_candidato_doador`) é membro é receita de um e despesa de outro: sai do total
    (`receita_repasses_internos`). Repasse com doador nulo **fica** e é reportado em
    `receita_repasses_doador_desconhecido` (pode ser interno; a tela mostra a faixa).

    Args:
        receitas: saída de `financeiro.classificar_receitas` com `sq_candidato_doador`.

    Raises:
        ValueError: coluna ausente (sem `sq_candidato_doador` não há como deduplicar).
    """
    exigir_colunas(
        receitas,
        [entidade, "categoria", "ds_origem_receita", "vr_receita", "sq_candidato_doador"],
        "receitas_grupo",
    )
    lista = list(membros)
    dos_membros = receitas.filter(pl.col(entidade).is_in(lista))
    repasse = expr_repasse_candidato(dos_membros)
    doador = pl.col("sq_candidato_doador")
    interna = repasse & doador.is_in(lista).fill_null(False)
    desconhecido = repasse & doador.is_null()
    valor = pl.col("vr_receita")
    extras = dos_membros.select(
        valor.filter(interna).sum().cast(pl.Float64).alias("receita_repasses_internos"),
        valor.filter(desconhecido)
        .sum()
        .cast(pl.Float64)
        .alias("receita_repasses_doador_desconhecido"),
    )
    return pl.concat(
        [resumo_receitas(dos_membros.filter(~interna), por=()), extras], how="horizontal"
    )
