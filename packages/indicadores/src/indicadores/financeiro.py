"""Indicadores financeiros (spec §4): receita por fonte, % público, % autofinanciamento,
composição e concentração das fontes, repasses entre candidatos, receita por voto e por mil
aptos, saldo, distribuição por candidato, comparação 2022→2026, custo por voto (contratado e
pago), dívida e correção pelo IPCA.

Rótulos do TSE são comparados normalizados (maiúsculas, sem acento, espaços colapsados),
porque a grafia muda entre anos; rótulo fora das tabelas fechadas abaixo **falha** — a lista
de valores distintos de 2022 e 2026 é fechada com o agente `dados` (spec §7 obs. c).
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence

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
    # 2026 (códigos 1003020x): repasse de outro candidato detalhado pela origem do dinheiro, com
    # fonte "Outros Recursos". Quando a origem nomeia um fundo, o recurso é público (spec §4.1).
    "FUNDO ESPECIAL DE FINANCIAMENTO DE CAMPANHA": "fefc",
    "FUNDO PARTIDARIO": "fundo_partidario",
    "DOACOES PARA CAMPANHA": "outros_candidatos",
    "RENDIMENTOS DE APLICACOES FINANCEIRAS": "outros",
    # Só 2022. Quem paga é o comprador; o fundo só custeou o bem vendido — não é recurso público.
    "COMERCIALIZACAO DE BENS COM OR": "outros",
    "COMERCIALIZACAO DE BENS COM FEFC": "outros",
    "RECURSOS DE ORIGENS NAO IDENTIFICADAS": "outros",
}
_NATUREZAS: dict[str, bool] = {"FINANCEIRO": True, "ESTIMAVEL": False, "ESTIMADO": False}
"""Natureza da receita normalizada → é financeira? O TSE grava "ESTIMÁVEL"; "ESTIMADO" fica como
sinônimo porque a view da API ainda converte um no outro (T-B03)."""

ORIGENS_REPASSE_CANDIDATO = frozenset(
    {
        "RECURSOS DE OUTROS CANDIDATOS",
        # 2026 (1003020x, fonte "Outros Recursos"): sempre de outro candidato (spec §4.1).
        "FUNDO ESPECIAL DE FINANCIAMENTO DE CAMPANHA",
        "FUNDO PARTIDARIO",
        "DOACOES PARA CAMPANHA",
    }
)
"""`DS_ORIGEM_RECEITA` normalizadas que são repasse de outra campanha (spec §4.6).

Reconhecido pela **origem**, não pela categoria: o FEFC repassado por outro candidato chega com
fonte FEFC e cai em `fefc`; filtrar por `outros_candidatos` deixaria passar o grosso do repasse.
"""

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


def _rotulos_em(serie: pl.Series, normalizados: frozenset[str]) -> list[str]:
    """Rótulos brutos de `serie` cuja forma normalizada está em `normalizados`."""
    return [
        r
        for r in serie.unique().to_list()
        if r is not None and normalizar_rotulo(r) in normalizados
    ]


def expr_repasse_candidato(receitas: pl.DataFrame) -> pl.Expr:
    """Expressão booleana: a linha de receita é repasse de outro candidato (spec §4.6)."""
    return pl.col("ds_origem_receita").is_in(
        _rotulos_em(receitas["ds_origem_receita"], ORIGENS_REPASSE_CANDIDATO)
    )


def _categoria(fonte: str | None, origem: str | None) -> str:
    if fonte is None or normalizar_rotulo(fonte) not in _FONTES:
        raise ValueError(f"ds_fonte_receita desconhecida: {fonte!r}")
    if origem is None or normalizar_rotulo(origem) not in _ORIGENS:
        raise ValueError(f"ds_origem_receita desconhecida: {origem!r}")
    # A fonte manda: o FEFC chega ao candidato com origem "Recursos de partido político". Só com
    # fonte "Outros Recursos" a origem decide — inclusive a origem que nomeia um fundo (2026).
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
    """Receita total, por natureza, por categoria, composição e concentração (§4.1, §4.5, §4.6).

    `receita_total = Σ vr_receita` (financeira + estimável); `receita_financeira` e
    `receita_estimavel` por natureza; `receita_<categoria>` para cada categoria (0 se ausente);
    `receita_repasses_candidatos` (pela origem) e `receita_sem_repasses = total − repasses`;
    `pct_publico = 100 × (fefc + fundo_partidario) / total`;
    `pct_autofinanciamento = 100 × recursos_proprios / total`;
    `pct_pessoa_fisica = 100 × (pessoa_fisica + financiamento_coletivo) / total`;
    `pct_estimavel = 100 × estimável / total`; `hhi_fontes = Σ s_c²` nas 8 categorias e
    `n_efetivo_fontes = 1 / hhi_fontes` (Laakso–Taagepera 1979). Total 0 → `null`.

    Args:
        receitas: saída de `classificar_receitas` com `ds_natureza_receita` e `vr_receita`.
        por: agrupamento; vazio = uma linha com o total de tudo (ex.: grupo).

    Raises:
        ValueError: natureza da receita desconhecida ou `vr_receita` negativa.
    """
    exigir_colunas(
        receitas,
        [*por, "categoria", "ds_origem_receita", "ds_natureza_receita", "vr_receita"],
        "resumo_receitas",
    )
    # Fatias e HHI só fazem sentido com parcelas não negativas (não ocorre em 2022/2026).
    if (receitas["vr_receita"] < 0).any():
        raise ValueError("resumo_receitas: vr_receita negativa")
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
        valor.filter(~financeira).sum().alias("receita_estimavel"),
        valor.filter(expr_repasse_candidato(receitas)).sum().alias("receita_repasses_candidatos"),
        *(
            valor.filter(pl.col("categoria") == c).sum().alias(f"receita_{c}")
            for c in CATEGORIAS_RECEITA
        ),
    ]
    tabela = (
        receitas.group_by(list(por)).agg(somas).sort(list(por)) if por else receitas.select(somas)
    )
    total = pl.col("receita_total")
    hhi = pl.sum_horizontal(razao(pl.col(f"receita_{c}"), total) ** 2 for c in CATEGORIAS_RECEITA)
    pessoa_fisica = pl.col("receita_pessoa_fisica") + pl.col("receita_financiamento_coletivo")
    return tabela.with_columns(
        (total - pl.col("receita_repasses_candidatos")).alias("receita_sem_repasses"),
        (100 * razao(pl.col("receita_fefc") + pl.col("receita_fundo_partidario"), total)).alias(
            "pct_publico"
        ),
        (100 * razao(pl.col("receita_recursos_proprios"), total)).alias("pct_autofinanciamento"),
        (100 * razao(pessoa_fisica, total)).alias("pct_pessoa_fisica"),
        (100 * razao(pl.col("receita_estimavel"), total)).alias("pct_estimavel"),
        # sum_horizontal ignora nulos (daria 0 com total 0): o null tem de ser explícito.
        pl.when(total > 0).then(hhi).otherwise(None).alias("hhi_fontes"),
    ).with_columns(razao(pl.lit(1.0), pl.col("hhi_fontes")).alias("n_efetivo_fontes"))


def despesa_campanha(
    despesas: pl.DataFrame,
    coluna_valor: str,
    por: Sequence[str] = ("sq_candidato",),
    *,
    incluir_transferencias: bool = False,
) -> pl.DataFrame:
    """Soma a despesa da própria campanha, sem repasses a outros candidatos/partidos (§4.2).

    Com `incluir_transferencias=True` soma também os repasses — é a despesa do **saldo**
    (§4.8): repassar é uso do dinheiro recebido, mas não custo da própria campanha.

    Serve às despesas contratadas (`vr_despesa_contratada`, por `sq_candidato`) e pagas
    (`vr_pagto_despesa`, por `sq_prestador_contas` — o arquivo de pagas não traz o candidato).
    Saída: `por…, despesa`.

    Raises:
        ValueError: `ds_origem_despesa` nula.
    """
    exigir_colunas(despesas, [*por, "ds_origem_despesa", coluna_valor], "despesa_campanha")
    if despesas["ds_origem_despesa"].null_count():
        raise ValueError("despesa_campanha: ds_origem_despesa nula")
    transferencias = (
        []
        if incluir_transferencias
        else _rotulos_em(despesas["ds_origem_despesa"], ORIGENS_DESPESA_TRANSFERENCIA)
    )
    proprias = despesas.filter(~pl.col("ds_origem_despesa").is_in(transferencias))
    soma = pl.col(coluna_valor).sum().alias("despesa")
    if not por:
        return proprias.select(soma)
    return proprias.group_by(list(por)).agg(soma).sort(list(por))


def _despesa_paga() -> pl.Expr:
    """`despesa_paga` com nulo → 0 quando há despesa contratada (contrato de entrada, §4.2).

    `despesas_pagas` não traz linha para quem ainda não pagou nada; com contas entregues
    (contratada não nula) isso é "pagou 0", não "sem dado". Sem contas, segue nulo.
    """
    contratada, paga = pl.col("despesa_contratada"), pl.col("despesa_paga")
    return (
        pl.when(paga.is_null() & contratada.is_not_null())
        .then(pl.lit(0.0))
        .otherwise(paga.cast(pl.Float64))
        .alias("despesa_paga")
    )


def custo_por_voto(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `custo_voto_contratado`, `custo_voto_pago` (R$/voto) e `divida` (§4.2).

    `custo = despesa / votos` (`votos = 0` → `null`, nunca infinito);
    `divida = despesa_contratada − despesa_paga`. `despesa_paga` nula com contratada não nula
    vira 0 (nenhum pagamento lançado); a coluna sai já normalizada.
    """
    exigir_colunas(df, ["despesa_contratada", "despesa_paga", "votos"], "custo_por_voto")
    return df.with_columns(_despesa_paga()).with_columns(
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
    df = df.with_columns(_despesa_paga())
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


def receita_por_voto(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `receita_por_voto = receita_total / votos` (R$/voto; spec §4.7).

    `votos = 0` → `null`; receita nula (sem contas) → `null`.
    """
    exigir_colunas(df, ["receita_total", "votos"], "receita_por_voto")
    return df.with_columns(
        razao(pl.col("receita_total"), pl.col("votos")).alias("receita_por_voto")
    )


def receita_por_voto_agregado(df: pl.DataFrame) -> pl.DataFrame:
    """Receita por voto do grupo: `Σ receita / Σ votos` (agregado, não média de razões; §4.7).

    Entram só candidatos com contas (`receita_total` não nula) e `votos > 0`. Saída (uma
    linha): `receita_por_voto`, `mediana_receita_por_voto`, `candidatos_sem_voto_excluidos`,
    `candidatos_sem_contas_excluidos` — mesma regra do custo por voto (§4.2).
    """
    exigir_colunas(df, ["receita_total", "votos"], "receita_por_voto_agregado")
    com_contas = pl.col("receita_total").is_not_null()
    elegivel = com_contas & (pl.col("votos") > 0)
    return df.select(
        razao(
            pl.col("receita_total").filter(elegivel).sum(), pl.col("votos").filter(elegivel).sum()
        ).alias("receita_por_voto"),
        (pl.col("receita_total") / pl.col("votos"))
        .filter(elegivel)
        .median()
        .alias("mediana_receita_por_voto"),
        (com_contas & (pl.col("votos") <= 0)).sum().alias("candidatos_sem_voto_excluidos"),
        (~com_contas).sum().alias("candidatos_sem_contas_excluidos"),
    )


def receita_por_mil_aptos(
    df: pl.DataFrame, receita: str = "receita_total", aptos: str = "aptos"
) -> pl.DataFrame:
    """Acrescenta `receita_por_mil_aptos = 1000 × receita / aptos` (spec §4.7).

    `aptos` é o eleitorado da circunscrição (UF; Brasil para presidente), contado **uma vez**
    por recorte — o chamador soma a receita dos membros antes. `aptos = 0` → `null`.
    """
    exigir_colunas(df, [receita, aptos], "receita_por_mil_aptos")
    return df.with_columns(
        (1000 * razao(pl.col(receita), pl.col(aptos))).alias("receita_por_mil_aptos")
    )


def saldo_campanha(df: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta `saldo_contratado`, `saldo_financeiro` e `pct_receita_gasta` (spec §4.8).

    `saldo_contratado = receita_total − despesa_contratada`;
    `saldo_financeiro = receita_financeira − despesa_paga`;
    `pct_receita_gasta = 100 × despesa_contratada / receita_total` (receita 0 → `null`).
    As despesas devem **incluir** repasses (`despesa_campanha(…, incluir_transferencias=True)`).
    `despesa_paga` nula com contratada não nula vira 0; sem despesa contratada, tudo `null`.
    """
    exigir_colunas(
        df,
        ["receita_total", "receita_financeira", "despesa_contratada", "despesa_paga"],
        "saldo_campanha",
    )
    contratada = pl.col("despesa_contratada")
    return df.with_columns(_despesa_paga()).with_columns(
        (pl.col("receita_total") - contratada).alias("saldo_contratado"),
        (pl.col("receita_financeira") - pl.col("despesa_paga")).alias("saldo_financeiro"),
        (100 * razao(contratada, pl.col("receita_total"))).alias("pct_receita_gasta"),
    )


def distribuicao_receita(df: pl.DataFrame, coluna: str = "receita_total") -> pl.DataFrame:
    """Distribuição por candidato do grupo: média, mediana, quartis e máximo (spec §4.9).

    Só candidatos com contas (`coluna` não nula; 0 entra) — sem contas não é receita zero.
    Quartis por interpolação linear. Saída (uma linha): `n_candidatos`, `n_com_contas`, `soma`,
    `media`, `mediana`, `p25`, `p75`, `maximo`; ninguém com contas → estatísticas `null`.
    """
    exigir_colunas(df, [coluna], "distribuicao_receita")
    valor = pl.col(coluna).drop_nulls().cast(pl.Float64)
    n_com_contas = pl.col(coluna).is_not_null().sum()
    return df.select(
        pl.len().alias("n_candidatos"),
        n_com_contas.alias("n_com_contas"),
        # A soma vazia do polars é 0; aqui "ninguém com contas" tem de ser null.
        pl.when(n_com_contas > 0).then(valor.sum()).otherwise(None).alias("soma"),
        valor.mean().alias("media"),
        valor.median().alias("mediana"),
        valor.quantile(0.25, interpolation="linear").alias("p25"),
        valor.quantile(0.75, interpolation="linear").alias("p75"),
        valor.max().alias("maximo"),
    )


def comparar_receitas(
    df: pl.DataFrame,
    monetarias: Iterable[str],
    percentuais: Iterable[str],
    serie: pl.DataFrame,
    mes_origem: str,
    mes_base: str,
) -> pl.DataFrame:
    """Compara 2022 → 2026 colunas `<c>_2022` e `<c>_2026` (spec §4.10).

    Monetárias: `<c>_2022` sai corrigida pelo IPCA de `mes_origem` a `mes_base` (o chamador
    passa o valor **nominal**, para não corrigir duas vezes); `delta_<c> = 2026 − 2022'` e
    `var_pct_<c> = 100 × (2026 / 2022' − 1)` (2022 nulo ou 0 → `null`). Percentuais: sem
    correção, só `delta_<c>` em p.p.

    Raises:
        ValueError: coluna ausente, coluna nas duas listas ou IPCA incompleto.
    """
    monet, perc = list(monetarias), list(percentuais)
    repetidas = set(monet) & set(perc)
    if repetidas:
        raise ValueError(f"comparar_receitas: coluna monetária e percentual {sorted(repetidas)}")
    todas = [*monet, *perc]
    exigir_colunas(df, [f"{c}_{ano}" for c in todas for ano in (2022, 2026)], "comparar_receitas")
    fator = fator_ipca(serie, mes_origem, mes_base)
    corrigido = df.with_columns(
        (pl.col(f"{c}_2022").cast(pl.Float64) * fator).alias(f"{c}_2022") for c in monet
    )
    return corrigido.with_columns(
        *((pl.col(f"{c}_2026") - pl.col(f"{c}_2022")).alias(f"delta_{c}") for c in todas),
        *(
            (100 * (razao(pl.col(f"{c}_2026"), pl.col(f"{c}_2022")) - 1)).alias(f"var_pct_{c}")
            for c in monet
        ),
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
