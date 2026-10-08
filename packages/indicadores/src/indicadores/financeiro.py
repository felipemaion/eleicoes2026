"""Indicadores financeiros (spec §4): receita por fonte, % público, % autofinanciamento,
custo por voto (contratado e pago), dívida e correção pelo IPCA.

Rótulos do TSE são comparados normalizados (maiúsculas, sem acento, espaços colapsados),
porque a grafia muda entre anos; rótulo fora das tabelas fechadas abaixo **falha** — a lista
de valores distintos de 2022 e 2026 é fechada com o agente `dados` (spec §7 obs. c).
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence

import polars as pl

from indicadores._comum import exigir_colunas, razao

CATEGORIAS_RECEITA = (
    "fefc",
    "fundo_partidario",
    "pessoa_fisica",
    "recursos_proprios",
    "financiamento_coletivo",
    "partido_outros_recursos",
    "outros_candidatos",
    "outros",
)
"""Categorias de receita da spec §4.1, na ordem de exibição."""

_FONTES: dict[str, str | None] = {
    "FUNDO ESPECIAL": "fefc",
    "FUNDO PARTIDARIO": "fundo_partidario",
    "OUTROS RECURSOS": None,  # a categoria sai da origem
}
_ORIGENS: dict[str, str] = {
    "RECURSOS DE PESSOAS FISICAS": "pessoa_fisica",
    "DOACOES PELA INTERNET": "pessoa_fisica",
    "RECURSOS PROPRIOS": "recursos_proprios",
    "RECURSOS DE FINANCIAMENTO COLETIVO": "financiamento_coletivo",
    "RECURSOS DE PARTIDO POLITICO": "partido_outros_recursos",
    "RECURSOS DE OUTROS CANDIDATOS": "outros_candidatos",
    "RENDIMENTOS DE APLICACOES FINANCEIRAS": "outros",
    "COMERCIALIZACAO DE BENS OU REALIZACAO DE EVENTOS": "outros",
    "RECURSOS DE ORIGENS NAO IDENTIFICADAS": "outros",
}
_NATUREZAS: dict[str, bool] = {"FINANCEIRO": True, "ESTIMADO": False}
"""Natureza da receita normalizada → é financeira?"""

ORIGENS_DESPESA_TRANSFERENCIA = frozenset({"DOACOES FINANCEIRAS A OUTROS CANDIDATOS/PARTIDOS"})
"""`DS_ORIGEM_DESPESA` que são repasse a terceiros, não custo da própria campanha (spec §4.2)."""

MES_ORIGEM_PADRAO = "2022-09"
MES_BASE_ALVO = "2026-09"
"""Decisão 1.6 / ADR 0007: set/2022 → set/2026 (com a emenda do último mês disponível)."""

_RE_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def normalizar_rotulo(rotulo: str) -> str:
    """Maiúsculas, sem acento e com espaços colapsados — para comparar rótulos do TSE."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", rotulo) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.upper().split())


def _categoria(fonte: str | None, origem: str | None) -> str:
    if fonte is None or normalizar_rotulo(fonte) not in _FONTES:
        raise ValueError(f"ds_fonte_receita desconhecida: {fonte!r}")
    if origem is None or normalizar_rotulo(origem) not in _ORIGENS:
        raise ValueError(f"ds_origem_receita desconhecida: {origem!r}")
    # A fonte manda: o FEFC chega ao candidato com origem "Recursos de partido político".
    return _FONTES[normalizar_rotulo(fonte)] or _ORIGENS[normalizar_rotulo(origem)]


def classificar_receitas(receitas: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `categoria` (uma de `CATEGORIAS_RECEITA`) a cada receita (spec §4.1).

    Primeiro a fonte (FEFC, Fundo Partidário), depois a origem.

    Raises:
        ValueError: fonte ou origem fora das tabelas fechadas (nada cai em "outros" por omissão).
    """
    exigir_colunas(receitas, ["ds_fonte_receita", "ds_origem_receita"], "classificar_receitas")
    pares = receitas.select("ds_fonte_receita", "ds_origem_receita").unique()
    mapa = pl.DataFrame(
        [(f, o, _categoria(f, o)) for f, o in pares.iter_rows()],
        schema={
            "ds_fonte_receita": receitas.schema["ds_fonte_receita"],
            "ds_origem_receita": receitas.schema["ds_origem_receita"],
            "categoria": pl.String,
        },
        orient="row",
    )
    return receitas.join(mapa, on=["ds_fonte_receita", "ds_origem_receita"], how="left")


def resumo_receitas(receitas: pl.DataFrame, por: Sequence[str] = ("sq_candidato",)) -> pl.DataFrame:
    """Receita total, financeira, por categoria, % público e % autofinanciamento (spec §4.1).

    `receita_total = Σ vr_receita` (financeira + estimável); `receita_financeira` só a natureza
    financeira; `receita_<categoria>` para cada categoria (0 se ausente);
    `pct_publico = 100 × (fefc + fundo_partidario) / total`;
    `pct_autofinanciamento = 100 × recursos_proprios / total`. Total 0 → `null`.

    Args:
        receitas: saída de `classificar_receitas` com `ds_natureza_receita` e `vr_receita`.
        por: agrupamento; vazio = uma linha com o total de tudo (ex.: grupo).

    Raises:
        ValueError: natureza da receita desconhecida.
    """
    exigir_colunas(
        receitas, [*por, "categoria", "ds_natureza_receita", "vr_receita"], "resumo_receitas"
    )
    naturezas = {}
    for rotulo in receitas["ds_natureza_receita"].unique().to_list():
        if rotulo is None or normalizar_rotulo(rotulo) not in _NATUREZAS:
            raise ValueError(f"ds_natureza_receita desconhecida: {rotulo!r}")
        naturezas[rotulo] = _NATUREZAS[normalizar_rotulo(rotulo)]
    valor = pl.col("vr_receita")
    financeira = pl.col("ds_natureza_receita").is_in([r for r, fin in naturezas.items() if fin])
    somas = [
        valor.sum().alias("receita_total"),
        valor.filter(financeira).sum().alias("receita_financeira"),
        *(
            valor.filter(pl.col("categoria") == c).sum().alias(f"receita_{c}")
            for c in CATEGORIAS_RECEITA
        ),
    ]
    tabela = (
        receitas.group_by(list(por)).agg(somas).sort(list(por)) if por else receitas.select(somas)
    )
    total = pl.col("receita_total")
    return tabela.with_columns(
        (100 * razao(pl.col("receita_fefc") + pl.col("receita_fundo_partidario"), total)).alias(
            "pct_publico"
        ),
        (100 * razao(pl.col("receita_recursos_proprios"), total)).alias("pct_autofinanciamento"),
    )


def despesa_campanha(
    despesas: pl.DataFrame, coluna_valor: str, por: Sequence[str] = ("sq_candidato",)
) -> pl.DataFrame:
    """Soma a despesa da própria campanha, sem repasses a outros candidatos/partidos (§4.2).

    Serve às despesas contratadas (`vr_despesa_contratada`, por `sq_candidato`) e pagas
    (`vr_pagto_despesa`, por `sq_prestador_contas` — o arquivo de pagas não traz o candidato).
    Saída: `por…, despesa`.

    Raises:
        ValueError: `ds_origem_despesa` nula.
    """
    exigir_colunas(despesas, [*por, "ds_origem_despesa", coluna_valor], "despesa_campanha")
    if despesas["ds_origem_despesa"].null_count():
        raise ValueError("despesa_campanha: ds_origem_despesa nula")
    transferencias = [
        r
        for r in despesas["ds_origem_despesa"].unique().to_list()
        if normalizar_rotulo(r) in ORIGENS_DESPESA_TRANSFERENCIA
    ]
    proprias = despesas.filter(~pl.col("ds_origem_despesa").is_in(transferencias))
    soma = pl.col(coluna_valor).sum().alias("despesa")
    if not por:
        return proprias.select(soma)
    return proprias.group_by(list(por)).agg(soma).sort(list(por))


def custo_por_voto(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `custo_voto_contratado`, `custo_voto_pago` (R$/voto) e `divida` (§4.2).

    `custo = despesa / votos` (`votos = 0` → `null`, nunca infinito);
    `divida = despesa_contratada − despesa_paga`.
    """
    exigir_colunas(df, ["despesa_contratada", "despesa_paga", "votos"], "custo_por_voto")
    return df.with_columns(
        razao(pl.col("despesa_contratada"), pl.col("votos")).alias("custo_voto_contratado"),
        razao(pl.col("despesa_paga"), pl.col("votos")).alias("custo_voto_pago"),
        (pl.col("despesa_contratada") - pl.col("despesa_paga")).alias("divida"),
    )


def custo_por_voto_agregado(df: pl.DataFrame) -> pl.DataFrame:
    """Custo por voto de um grupo: `Σ despesa / Σ votos` (agregado, não média de razões; §4.2).

    Entram só candidatos com contas (`despesa_contratada` não nula) e `votos > 0`. Saída (uma
    linha): `custo_voto_contratado`, `custo_voto_pago`, `mediana_custo_voto_contratado`
    (distribuição por candidato tem cauda pesada), `candidatos_sem_voto_excluidos`,
    `candidatos_sem_contas_excluidos`.
    """
    exigir_colunas(df, ["despesa_contratada", "despesa_paga", "votos"], "custo_por_voto_agregado")
    com_contas = pl.col("despesa_contratada").is_not_null()
    elegivel = com_contas & (pl.col("votos") > 0)
    votos = pl.col("votos").filter(elegivel).sum()
    return df.select(
        razao(pl.col("despesa_contratada").filter(elegivel).sum(), votos).alias(
            "custo_voto_contratado"
        ),
        razao(pl.col("despesa_paga").filter(elegivel).sum(), votos).alias("custo_voto_pago"),
        (pl.col("despesa_contratada") / pl.col("votos"))
        .filter(elegivel)
        .median()
        .alias("mediana_custo_voto_contratado"),
        (com_contas & (pl.col("votos") <= 0)).sum().alias("candidatos_sem_voto_excluidos"),
        (~com_contas).sum().alias("candidatos_sem_contas_excluidos"),
    )


def _mes(rotulo: str) -> tuple[int, int]:
    if not _RE_MES.match(rotulo):
        raise ValueError(f"mês deve ser AAAA-MM: {rotulo!r}")
    ano, mes = rotulo.split("-")
    return int(ano), int(mes)


def serie_ipca(variacoes: Mapping[str, float]) -> pl.DataFrame:
    """Série SGS 433 (variação % mensal) como DataFrame `mes` ("AAAA-MM"), `variacao`."""
    for mes in variacoes:
        _mes(mes)
    return pl.DataFrame(
        {"mes": list(variacoes), "variacao": [float(v) for v in variacoes.values()]},
        schema={"mes": pl.String, "variacao": pl.Float64},
    ).sort("mes")


def fator_ipca(serie: pl.DataFrame, mes_origem: str, mes_base: str) -> float:
    """Fator de correção `Π_{m = origem+1}^{base} (1 + v_m / 100)` (spec §4.3).

    SGS 433 é **variação % mensal**, não índice. `origem = base` → 1.

    Raises:
        ValueError: mês mal formado, base anterior à origem ou mês ausente na série.
    """
    exigir_colunas(serie, ["mes", "variacao"], "fator_ipca")
    ano, mes = _mes(mes_origem)
    fim = _mes(mes_base)
    if fim < (ano, mes):
        raise ValueError(f"mês-base {mes_base} anterior à origem {mes_origem}")
    variacoes = dict(serie.select("mes", "variacao").iter_rows())
    fator = 1.0
    while (ano, mes) < fim:
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
        chave = f"{ano:04d}-{mes:02d}"
        if chave not in variacoes or variacoes[chave] is None:
            raise ValueError(f"IPCA ausente para {chave}")
        fator *= 1 + variacoes[chave] / 100
    return fator


def resolver_mes_base(
    serie: pl.DataFrame, mes_origem: str = MES_ORIGEM_PADRAO, alvo: str = MES_BASE_ALVO
) -> str:
    """Mês-base efetivo: o `alvo` se já publicado, senão o último mês da série (emenda ADR 0007).

    A interface deve declarar o mês devolvido ("R$ de <mês/ano>").

    Raises:
        ValueError: a série não tem nenhum mês posterior à origem.
    """
    _mes(mes_origem)
    _mes(alvo)
    posteriores = serie.filter(pl.col("mes") > mes_origem)["mes"]
    if posteriores.is_empty():
        raise ValueError(f"série IPCA sem meses posteriores à origem {mes_origem}")
    ultimo = str(posteriores.max())
    return alvo if alvo <= ultimo else ultimo


def corrigir_ipca(
    df: pl.DataFrame, coluna: str, serie: pl.DataFrame, mes_origem: str, mes_base: str
) -> pl.DataFrame:
    """Multiplica `coluna` pelo fator IPCA de `mes_origem` a `mes_base` (spec §4.3)."""
    exigir_colunas(df, [coluna], "corrigir_ipca")
    fator = fator_ipca(serie, mes_origem, mes_base)
    return df.with_columns((pl.col(coluna).cast(pl.Float64) * fator).alias(coluna))
