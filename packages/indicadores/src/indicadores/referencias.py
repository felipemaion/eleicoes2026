"""Comparação com candidatos de referência (spec §10, T-A11).

Dois passos, ambos funções puras:

1. `selecionar_eleitos` — regra dos "5 eleitos mais votados de outros partidos" por cargo e UF
   (§10.1). A lista editorial de presidenciáveis não passa por aqui: vem de `config/grupos.yaml`.
2. `perfil_relativo` — cada indicador do catálogo `PERFIL` (§10.3) dos nossos contra a
   **mediana** da referência no mesmo cargo e UF: razão, diferença em p.p. ou só contexto.

Comparar exige o mesmo cargo (e ano): presidente × deputado ou 2022 × 2026 falham alto.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Literal

import polars as pl

from indicadores._colunas import CD_CARGO, DS_SIT_TOT_TURNO, NR_PARTIDO
from indicadores._comum import exigir_colunas, exigir_unicidade, razao
from indicadores.financeiro import normalizar_rotulo

TipoIndice = Literal["razao", "diferenca_pp", "contexto"]

PERFIL: Mapping[str, TipoIndice] = MappingProxyType(
    {
        "votos": "contexto",
        "pct_validos": "contexto",
        "penetracao": "razao",
        "n_municipios_com_voto": "contexto",
        "pct_maiores": "diferenca_pp",
        "n_efetivo_municipios": "razao",
        "custo_voto_pago": "razao",
        "receita_total": "contexto",
        "receita_por_voto": "razao",
        "pct_publico": "diferenca_pp",
        "pct_pessoa_fisica": "diferenca_pp",
        "pct_autofinanciamento": "diferenca_pp",
    }
)
"""Catálogo do perfil comparável, na ordem de exibição (spec §10.3; testado contra a tabela)."""

N_REFERENCIA = 5
"""Eleitos de outros partidos por cargo e UF (pedido de 14/10)."""

PARTIDO_MISSAO = 14
"""Número do Missão em 2026 — em 2022 o 14 era do PTB (spec §10.1): não usar o padrão em 2022."""

MINIMO_REFERENCIA = 3
"""Valores não nulos exigidos para a mediana da referência: a maioria dos 5 (spec §10.3)."""

SITUACOES_ELEITO = frozenset({"ELEITO", "ELEITO POR QP", "ELEITO POR MEDIA"})
SITUACOES_NAO_ELEITO = frozenset({"NAO ELEITO", "SUPLENTE", "2O TURNO"})
"""Rótulos normalizados de `ds_sit_tot_turno` (o "º" de "2º TURNO" vira "O" na NFKD)."""

POR_PADRAO = (CD_CARGO, "sg_uf")


def _rotulos_eleito(situacoes: pl.Series) -> list[str]:
    """Rótulos brutos que significam eleito; falha alto com rótulo fora da lista conhecida."""
    normalizados = {r: normalizar_rotulo(r) for r in situacoes.drop_nulls().unique().to_list()}
    conhecidos = SITUACOES_ELEITO | SITUACOES_NAO_ELEITO
    desconhecidos = sorted(r for r, n in normalizados.items() if n not in conhecidos)
    if desconhecidos:
        raise ValueError(f"selecionar_eleitos: situação desconhecida {desconhecidos}")
    return [r for r, n in normalizados.items() if n in SITUACOES_ELEITO]


def selecionar_eleitos(
    candidatos: pl.DataFrame,
    n: int = N_REFERENCIA,
    excluir_partidos: Sequence[int] = (PARTIDO_MISSAO,),
    excluir_sq: Sequence[int] = (),
    por: Sequence[str] = POR_PADRAO,
) -> pl.DataFrame:
    """Os `n` eleitos mais votados de outros partidos em cada recorte `por` (spec §10.1).

    Eleito = `ds_sit_tot_turno` normalizado em `SITUACOES_ELEITO`; situação nula (não
    totalizado) não é eleito. Ordem: `votos` decrescente, empate por `sq_candidato` crescente.
    Recorte sem eleito de outro partido não aparece na saída.

    Args:
        candidatos: uma linha por candidatura com `por…, sq_candidato, nr_partido,
            ds_sit_tot_turno, votos` (nominais válidos totais do recorte, 1º turno).
        n: quantos eleitos ficam por recorte.
        excluir_partidos: `nr_partido` excluídos (padrão: Missão; em 2022 passar `()`).
        excluir_sq: candidaturas excluídas (membros do grupo comparado).
        por: recorte do ranking (padrão cargo e UF).

    Returns:
        `por…, posicao, sq_candidato, nr_partido, votos`, ordenado por `por…, posicao`.

    Raises:
        ValueError: `n < 1`, coluna ausente, candidatura repetida, situação desconhecida ou
            eleito com `votos` nulo.
    """
    if n < 1:
        raise ValueError(f"selecionar_eleitos: n deve ser ≥ 1 (recebido {n})")
    contexto = "selecionar_eleitos"
    exigir_colunas(
        candidatos, [*por, "sq_candidato", NR_PARTIDO, DS_SIT_TOT_TURNO, "votos"], contexto
    )
    exigir_unicidade(candidatos, [*por, "sq_candidato"], contexto)
    rotulos = _rotulos_eleito(candidatos[DS_SIT_TOT_TURNO])
    eleitos = candidatos.filter(pl.col(DS_SIT_TOT_TURNO).is_in(rotulos))
    sem_votos = eleitos.filter(pl.col("votos").is_null())
    if sem_votos.height:
        raise ValueError(f"{contexto}: eleito sem votos {sorted(sem_votos['sq_candidato'])}")
    # `is_in` com lista vazia perde o tipo; só filtra quando há o que excluir.
    if excluir_partidos:
        eleitos = eleitos.filter(~pl.col(NR_PARTIDO).is_in(list(excluir_partidos)))
    if excluir_sq:
        eleitos = eleitos.filter(~pl.col("sq_candidato").is_in(list(excluir_sq)))
    decrescente = [*([False] * len(por)), True, False]
    posicao = pl.int_range(pl.len(), dtype=pl.Int64).over(list(por)) + 1
    return (
        eleitos.sort([*por, "votos", "sq_candidato"], descending=decrescente)
        .with_columns(posicao.alias("posicao"))
        .filter(pl.col("posicao") <= n)
        .select(*por, "posicao", "sq_candidato", NR_PARTIDO, "votos")
    )


def _exigir_catalogo(indicadores: Sequence[str], contexto: str) -> None:
    if not indicadores:
        raise ValueError(f"{contexto}: nenhum indicador pedido")
    fora = [i for i in indicadores if i not in PERFIL]
    if fora:
        raise ValueError(f"{contexto}: indicador fora do perfil {fora} (spec §10.3)")


def _longo(df: pl.DataFrame, indice: Sequence[str], indicadores: Sequence[str]) -> pl.DataFrame:
    """Formato longo `indice…, indicador, valor` com valores em Float64 (unpivot exige um tipo)."""
    return df.select(*indice, *(pl.col(i).cast(pl.Float64) for i in indicadores)).unpivot(
        index=list(indice), on=list(indicadores), variable_name="indicador", value_name="valor"
    )


def _ordem_catalogo() -> pl.Expr:
    return pl.col("indicador").replace_strict(
        {nome: posicao for posicao, nome in enumerate(PERFIL)}, return_dtype=pl.Int64
    )


def mediana_referencia(
    referencia: pl.DataFrame,
    indicadores: Sequence[str],
    por: Sequence[str] = POR_PADRAO,
    minimo: int = MINIMO_REFERENCIA,
) -> pl.DataFrame:
    """Mediana dos valores não nulos de cada indicador por recorte (spec §10.3).

    Menos de `minimo` valores → mediana nula, com `n` informado. Para a mediana dos nossos
    (número-resumo do Missão no recorte) use `minimo=1`.

    Returns:
        `por…, indicador, mediana, n`, na ordem do catálogo.

    Raises:
        ValueError: `minimo < 1`, indicador fora do catálogo ou coluna ausente.
    """
    if minimo < 1:
        raise ValueError(f"mediana_referencia: minimo deve ser ≥ 1 (recebido {minimo})")
    _exigir_catalogo(indicadores, "mediana_referencia")
    exigir_colunas(referencia, [*por, *indicadores], "mediana_referencia")
    return (
        _longo(referencia, por, indicadores)
        .group_by([*por, "indicador"])
        .agg(
            pl.col("valor").median().alias("_mediana"),
            pl.col("valor").count().cast(pl.Int64).alias("n"),
        )
        .with_columns(
            pl.when(pl.col("n") >= minimo).then(pl.col("_mediana")).alias("mediana"),
            _ordem_catalogo().alias("_ordem"),
        )
        .sort([*por, "_ordem"])
        .select(*por, "indicador", "mediana", "n")
    )


def _exigir_um_ano(frames: Sequence[pl.DataFrame], por: Sequence[str]) -> None:
    """Sem o ano no recorte, nossos e referência precisam ser do mesmo (único) ano."""
    if "ano_eleicao" in por:
        return
    anos = {a for df in frames if "ano_eleicao" in df.columns for a in df["ano_eleicao"].unique()}
    if len(anos) > 1:
        raise ValueError(f"perfil_relativo: um ano por vez (ano_eleicao com {sorted(anos)})")


def perfil_relativo(
    nossos: pl.DataFrame,
    referencia: pl.DataFrame,
    indicadores: Sequence[str] = tuple(PERFIL),
    por: Sequence[str] = POR_PADRAO,
    entidade: str = "sq_candidato",
    minimo: int = MINIMO_REFERENCIA,
) -> pl.DataFrame:
    """Índice de cada um dos `nossos` relativo à mediana da `referencia` (spec §10.3).

    `razao`: `valor / mediana` (mediana 0 ou nula → nulo); `diferenca_pp`: `valor − mediana`;
    `contexto`: índice nulo, mediana mostrada. Recorte dos nossos sem referência →
    `n_referencia = 0` e mediana nula.

    Args:
        nossos: uma linha por entidade (candidato, ou o grupo) com `por…, entidade, indicadores…`.
        referencia: os candidatos de referência com `por…, indicadores…`.
        indicadores: subconjunto do catálogo `PERFIL` (padrão: todos).
        por: recorte da comparação; precisa conter `cd_cargo`.
        entidade: coluna que identifica cada um dos nossos.
        minimo: valores não nulos exigidos para a mediana da referência.

    Returns:
        `por…, entidade, indicador, tipo, valor, mediana_referencia, n_referencia, indice`.

    Raises:
        ValueError: `por` sem `cd_cargo` (um cargo por vez), anos misturados fora de `por`,
            indicador fora do catálogo, coluna ausente ou entidade repetida no recorte.
    """
    contexto = "perfil_relativo"
    if CD_CARGO not in por:
        raise ValueError(f"{contexto}: um cargo por vez — `por` precisa conter {CD_CARGO}")
    _exigir_catalogo(indicadores, contexto)
    exigir_colunas(nossos, [*por, entidade, *indicadores], contexto)
    exigir_colunas(referencia, [*por, *indicadores], contexto)
    _exigir_um_ano((nossos, referencia), por)
    exigir_unicidade(nossos, [*por, entidade], contexto)
    medianas = mediana_referencia(referencia, indicadores, por, minimo).rename(
        {"mediana": "mediana_referencia", "n": "n_referencia"}
    )
    tipo = pl.col("indicador").replace_strict(dict(PERFIL), return_dtype=pl.String)
    valor, mediana = pl.col("valor"), pl.col("mediana_referencia")
    indice = (
        pl.when(pl.col("tipo") == "razao")
        .then(razao(valor, mediana))
        .when(pl.col("tipo") == "diferenca_pp")
        .then(valor - mediana)
        .otherwise(pl.lit(None, dtype=pl.Float64))
    )
    return (
        _longo(nossos, [*por, entidade], indicadores)
        .join(medianas, on=[*por, "indicador"], how="left")
        .with_columns(tipo.alias("tipo"), pl.col("n_referencia").fill_null(0))
        .with_columns(indice.alias("indice"), _ordem_catalogo().alias("_ordem"))
        .sort([*por, entidade, "_ordem"])
        .select(
            *por,
            entidade,
            "indicador",
            "tipo",
            "valor",
            "mediana_referencia",
            "n_referencia",
            "indice",
        )
    )
