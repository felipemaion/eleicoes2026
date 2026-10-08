"""Contratos da prestação de contas (TSE) e da série IPCA (BCB).

Grão: **lançamentos agregados** por candidatura × prestação × rótulos. ``SQ_RECEITA`` e
``SQ_DESPESA`` não são chaves (2022: 674.944 linhas de receita para 665.131 pares
prestador×receita), então o lançamento cru não tem chave natural; agregar elimina também os
dados de doadores/fornecedores (pessoas físicas) do Parquet. A soma de ``vr_*`` e a de
``qt_lancamentos`` batem com o CSV de origem (total de controle). Rótulos ``ds_*`` seguem
brutos (só espaços normalizados): quem classifica é ``indicadores.financeiro``.
"""

from __future__ import annotations

import polars as pl

from contratos.modelo import Contrato

I8, I16, I32, I64 = pl.Int8, pl.Int16, pl.Int32, pl.Int64
TXT, DEC, DATA = pl.Utf8, pl.Float64, pl.Date

_PRESTACAO = {
    "ano_eleicao": I16, "nr_turno": I8, "cd_eleicao": I32, "sg_uf": TXT,
    "sq_prestador_contas": I64, "tp_prestacao_contas": TXT, "dt_prestacao_contas": DATA,
}  # fmt: skip
_CANDIDATURA = {
    "sq_candidato": I64, "cd_cargo": I8, "nr_partido": I16, "sg_partido": TXT,
}  # fmt: skip
_ORIGEM = {"nr_turno": "ST_TURNO", "ano_eleicao": "AA_ELEICAO"}
_OBRIGATORIAS = (
    "ano_eleicao", "nr_turno", "cd_eleicao", "sg_uf", "sq_prestador_contas", "sq_candidato",
    "qt_lancamentos", "dt_geracao",
)  # fmt: skip
_CHAVE_BASE = (
    "ano_eleicao", "cd_eleicao", "nr_turno", "sg_uf", "sq_prestador_contas",
    "tp_prestacao_contas", "dt_prestacao_contas",
)  # fmt: skip

RECEITAS_CANDIDATOS = Contrato(
    nome="receitas_candidatos",
    colunas={
        **_PRESTACAO, **_CANDIDATURA, "ds_fonte_receita": TXT, "ds_origem_receita": TXT,
        "ds_natureza_receita": TXT, "vr_receita": DEC, "qt_lancamentos": I32, "dt_geracao": DATA,
    },
    chave=(*_CHAVE_BASE, "ds_fonte_receita", "ds_origem_receita", "ds_natureza_receita"),
    nao_nulas=(*_OBRIGATORIAS, "vr_receita"),
    derivadas=frozenset({"qt_lancamentos"}),
    origem=_ORIGEM,
)  # fmt: skip

DESPESAS_CONTRATADAS_CANDIDATOS = Contrato(
    nome="despesas_contratadas_candidatos",
    colunas={
        **_PRESTACAO, **_CANDIDATURA, "ds_origem_despesa": TXT, "vr_despesa_contratada": DEC,
        "qt_lancamentos": I32, "dt_geracao": DATA,
    },
    chave=(*_CHAVE_BASE, "ds_origem_despesa"),
    nao_nulas=(*_OBRIGATORIAS, "vr_despesa_contratada"),
    derivadas=frozenset({"qt_lancamentos"}),
    origem=_ORIGEM,
)  # fmt: skip

# O arquivo de despesas pagas não traz SQ_CANDIDATO: o ETL liga por SQ_PRESTADOR_CONTAS
# (mapa tirado de receitas + despesas contratadas do mesmo ano; falta de elo é erro).
DESPESAS_PAGAS_CANDIDATOS = Contrato(
    nome="despesas_pagas_candidatos",
    colunas={
        **_PRESTACAO, "sq_candidato": I64, "ds_fonte_despesa": TXT, "ds_origem_despesa": TXT,
        "vr_pagto_despesa": DEC, "qt_lancamentos": I32, "dt_geracao": DATA,
    },
    chave=(*_CHAVE_BASE, "ds_fonte_despesa", "ds_origem_despesa"),
    nao_nulas=(*_OBRIGATORIAS, "vr_pagto_despesa"),
    derivadas=frozenset({"qt_lancamentos", "sq_candidato"}),
    origem=_ORIGEM,
)  # fmt: skip

# SGS 433 é variação % mensal; ``indice`` acumula a partir de 100 em dez/1979.
IPCA = Contrato(
    nome="ipca",
    colunas={"mes": TXT, "variacao": DEC, "indice": DEC},
    chave=("mes",),
    nao_nulas=("mes", "variacao", "indice"),
)

CONTRATOS_CONTAS: dict[str, Contrato] = {
    c.nome: c
    for c in (
        RECEITAS_CANDIDATOS, DESPESAS_CONTRATADAS_CANDIDATOS, DESPESAS_PAGAS_CANDIDATOS, IPCA,
    )
}  # fmt: skip
