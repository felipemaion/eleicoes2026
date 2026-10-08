"""Finanças de campanha: despesas, receitas e custo por voto, com correção pelo IPCA.

Orquestração: lê do Repositorio, monta DataFrames e chama `indicadores.financeiro/grupos`.
Nenhuma fórmula local (spec §4); transferências e doações internas saem nas funções da lib.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl
from indicadores import financeiro, grupos
from pydantic import BaseModel, Field

from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.escopo import BasesPorEscopo

ANO_NOMINAL = 2026  # valores de 2026 ficam nominais; anteriores sobem para o mês-base


class ResumoCustoCandidato(BaseModel):
    """Despesa (sem transferências) e custo por voto de um candidato."""

    despesa_contratada: float = Field(description="R$ da própria campanha, sem repasses.")
    despesa_paga: float = Field(description="R$ pagos da própria campanha, sem repasses.")
    divida: float = Field(description="contratada − paga (§4.2).")
    votos: int
    custo_voto_contratado: float | None = Field(
        description="R$/voto = despesa contratada ÷ votos nominais. "
        "Exclui repasses a outros candidatos/partidos (§4.2). null se votos = 0."
    )
    custo_voto_pago: float | None = Field(
        description="R$/voto pago; exclui repasses a outros candidatos/partidos (§4.2)."
    )


class FaixaReceita(BaseModel):
    """Intervalo honesto da receita do grupo quando há repasse de doador desconhecido (§4.6)."""

    minima: float = Field(description="Total − repasses de candidato com doador desconhecido.")
    maxima: float = Field(description="Total (todos os repasses desconhecidos são externos).")


class ResumoReceitasOut(BaseModel):
    """Receita por categoria (§4.1), composição (§4.5) e repasses entre candidatos (§4.6)."""

    por_categoria: dict[str, float]
    receita_total: float = Field(description="Σ das receitas; no grupo, sem repasses internos.")
    receita_financeira: float
    receita_estimavel: float = Field(description="Bens e serviços doados, não passam pela conta.")
    receita_repasses_candidatos: float = Field(description="Σ recebido de outros candidatos.")
    receita_sem_repasses: float = Field(description="receita_total − repasses de candidatos.")
    receita_repasses_internos: float | None = Field(
        description="Só no grupo: repasses entre membros, descontados do total (§4.6)."
    )
    receita_repasses_doador_desconhecido: float | None = Field(
        description="Só no grupo: repasses sem doador identificado; ficam no total."
    )
    faixa_receita: FaixaReceita | None = Field(description="Só no grupo; ver `FaixaReceita`.")
    pct_publico: float | None = Field(description="FEFC + Fundo Partidário, % da receita total.")
    pct_autofinanciamento: float | None
    pct_pessoa_fisica: float | None = Field(
        description="Pessoas físicas + financiamento coletivo, % da receita total (§4.5)."
    )
    pct_estimavel: float | None
    hhi_fontes: float | None = Field(description="Σ (parte da categoria)²; 1 = uma fonte só.")
    n_efetivo_fontes: float | None = Field(description="1 / HHI: nº de fontes equivalentes.")


class ReceitaPorVotoGrupo(BaseModel):
    """Receita por voto do grupo: Σ receita ÷ Σ votos, sobre candidatos com contas e voto (§4.7)."""

    receita_por_voto: float | None
    mediana_receita_por_voto: float | None
    candidatos_sem_voto_excluidos: int
    candidatos_sem_contas_excluidos: int


class DistribuicaoReceita(BaseModel):
    """Receita por candidato do grupo: cauda pesada, então média e mediana juntas (§4.9)."""

    n_candidatos: int
    n_com_contas: int
    soma: float | None
    media: float | None
    mediana: float | None
    p25: float | None
    p75: float | None
    maximo: float | None


class SaldoGrupo(BaseModel):
    """Saldo (§4.8). Receita bruta e despesa com repasses: repasses internos se anulam."""

    saldo_contratado: float | None = Field(description="receita − despesa contratada.")
    saldo_financeiro: float | None = Field(description="receita financeira − despesa paga.")
    pct_receita_gasta: float | None = Field(description="100 × despesa contratada ÷ receita.")


class ResumoCustoGrupo(BaseModel):
    """Agregado: Σ despesa / Σ votos, não média de razões (§4.2)."""

    despesa_contratada: float = Field(description="Σ da própria campanha, sem repasses.")
    despesa_paga: float = Field(description="Σ paga da própria campanha, sem repasses.")
    divida: float
    votos: int
    custo_voto_contratado: float | None = Field(
        description="Σ despesa contratada ÷ Σ votos; exclui repasses a outros "
        "candidatos/partidos (§4.2)."
    )
    custo_voto_pago: float | None = Field(
        description="Σ despesa paga ÷ Σ votos; exclui repasses a outros candidatos/partidos."
    )
    mediana_custo_voto_contratado: float | None = Field(
        description="Mediana entre candidatos com voto; exclui repasses (§4.2)."
    )
    candidatos_sem_voto_excluidos: int


@dataclass(frozen=True)
class ContasCand:
    """Contas de um candidato com a candidatura."""

    candidatura: Candidatura
    custo: ResumoCustoCandidato
    receita_total: float
    repasses_contratados: float
    repasses_pagos: float
    resumo: dict[str, float | None]  # `resumo_receitas` do candidato (bruto, §4.1/§4.5/§4.6)
    receita_por_voto: float | None = None
    receita_por_mil_aptos: float | None = None
    saldo_contratado: float | None = None
    saldo_financeiro: float | None = None
    pct_receita_gasta: float | None = None

    @property
    def pct_publico(self) -> float | None:
        """FEFC + Fundo Partidário, % da receita."""
        return self.resumo.get("pct_publico")

    @property
    def pct_autofinanciamento(self) -> float | None:
        """Recursos próprios, % da receita."""
        return self.resumo.get("pct_autofinanciamento")


@dataclass(frozen=True)
class ContasAgregadas:
    """Contas de um conjunto de candidaturas."""

    por_candidato: list[ContasCand]
    agregado: ResumoCustoGrupo
    receitas: ResumoReceitasOut
    receita_por_voto: ReceitaPorVotoGrupo
    distribuicao: DistribuicaoReceita
    saldo: SaldoGrupo
    receita_por_mil_aptos: float | None  # None com mais de um cargo (eleitorados não se somam)
    aptos: int | None
    parcial: bool
    base_ipca: str | None


_ESQUEMA_DESPESA = {
    "sq_candidato": pl.Int64,
    "ds_origem_despesa": pl.String,
    "vr_despesa_contratada": pl.Float64,
    "vr_despesa_paga": pl.Float64,
}
_ESQUEMA_RECEITA = {
    "sq_candidato": pl.Int64,
    "ds_fonte_receita": pl.String,
    "ds_origem_receita": pl.String,
    "ds_natureza_receita": pl.String,
    "vr_receita": pl.Float64,
    "sq_candidato_doador": pl.Int64,
}


_COLUNAS_DESPESA = (
    "despesa_contratada",
    "despesa_paga",
    "despesa_total_contratada",
    "despesa_total_paga",
    "repasse_contratado",
    "repasse_pago",
)


def _repasses(despesas: pl.DataFrame, coluna_valor: str, nome: str) -> pl.DataFrame:
    """Σ dos repasses a outros candidatos/partidos por candidato — o que o custo por voto exclui.

    Mesmos rótulos que `financeiro.despesa_campanha` descarta (spec §4.2), para que
    `despesa própria + repasses = despesa total` feche exatamente.
    """
    rotulos = [
        r
        for r in despesas["ds_origem_despesa"].unique().to_list()
        if financeiro.normalizar_rotulo(r) in financeiro.ORIGENS_DESPESA_TRANSFERENCIA
    ]
    return (
        despesas.filter(pl.col("ds_origem_despesa").is_in(rotulos))
        .group_by("sq_candidato")
        .agg(pl.col(coluna_valor).sum().alias(nome))
    )


def _correcao(repo: Repositorio, ano: int) -> tuple[pl.DataFrame, str, str] | None:
    """(série, mês de origem, mês-base efetivo) ou `None` se o ano é nominal.

    O mês-base é o do ADR 0007 se já publicado, senão o último disponível — e a resposta o
    declara (`base_ipca`). Sem série utilizável não se publica 2022 "nominal" por engano.
    """
    if ano >= ANO_NOMINAL:
        return None
    serie = financeiro.serie_ipca({v.mes: v.variacao for v in repo.ipca()})
    origem = f"{ano}-09"
    try:
        return serie, origem, financeiro.resolver_mes_base(serie, origem)
    except ValueError as erro:
        raise DadosIndisponiveis(str(erro)) from erro


def _corrigir(
    df: pl.DataFrame, colunas: Sequence[str], correcao: tuple[pl.DataFrame, str, str] | None
) -> pl.DataFrame:
    if correcao is None:
        return df
    serie, origem, base = correcao
    try:
        for coluna in colunas:
            df = financeiro.corrigir_ipca(df, coluna, serie, origem, base)
    except ValueError as erro:  # mês faltando na série
        raise DadosIndisponiveis(str(erro)) from erro
    return df


def correcao_do_ano(repo: Repositorio, ano: int) -> tuple[pl.DataFrame, str, str] | None:
    """Série, mês de origem e mês-base da correção do ano (`None` se nominal)."""
    return _correcao(repo, ano)


def contas_de(
    repo: Repositorio,
    ano: int,
    candidaturas: Sequence[Candidatura],
    *,
    nominal: bool = False,
) -> ContasAgregadas:
    """Contas das candidaturas no ano; só entram candidatos com lançamentos.

    `nominal=True` devolve os valores sem IPCA: a comparação 2022→2026 (`comparar_receitas`)
    corrige 2022 por conta própria, e corrigir antes dobraria a correção (spec §4.10).
    """
    sqs = [c.sq_candidato for c in candidaturas]
    correcao = None if nominal else _correcao(repo, ano)
    votos = repo.votos_totais(ano, sqs)
    despesas = pl.DataFrame(
        [
            (d.sq_candidato, d.ds_origem_despesa, d.contratada, d.paga)
            for d in repo.despesas(ano, sqs)
        ],
        schema=_ESQUEMA_DESPESA,
        orient="row",
    )
    receitas = pl.DataFrame(
        [
            (r.sq_candidato, r.ds_fonte_receita, r.ds_origem_receita, r.ds_natureza_receita,
             r.valor, r.sq_candidato_doador)
            for r in repo.receitas(ano, sqs)
        ],
        schema=_ESQUEMA_RECEITA,
        orient="row",
    )  # fmt: skip
    receitas = _corrigir(receitas, ["vr_receita"], correcao)
    com_contas = set(despesas["sq_candidato"]) | set(receitas["sq_candidato"])

    contratada = financeiro.despesa_campanha(despesas, "vr_despesa_contratada").rename(
        {"despesa": "despesa_contratada"}
    )
    paga = financeiro.despesa_campanha(despesas, "vr_despesa_paga").rename(
        {"despesa": "despesa_paga"}
    )
    total_contratada = financeiro.despesa_campanha(
        despesas, "vr_despesa_contratada", incluir_transferencias=True
    ).rename({"despesa": "despesa_total_contratada"})
    total_paga = financeiro.despesa_campanha(
        despesas, "vr_despesa_paga", incluir_transferencias=True
    ).rename({"despesa": "despesa_total_paga"})
    repasse_contratado = _repasses(despesas, "vr_despesa_contratada", "repasse_contratado")
    repasse_pago = _repasses(despesas, "vr_despesa_paga", "repasse_pago")
    tem_contas = pl.col("sq_candidato").is_in(list(com_contas))
    # Quem tem lançamentos mas só repasses fica com despesa 0; quem não tem contas fica null
    # (a lib exclui "sem contas" do agregado).
    base = (
        pl.DataFrame(
            {"sq_candidato": sqs, "votos": [votos.get(sq, 0) for sq in sqs]},
            schema={"sq_candidato": pl.Int64, "votos": pl.Int64},
        )
        .join(contratada, on="sq_candidato", how="left")
        .join(paga, on="sq_candidato", how="left")
        .join(total_contratada, on="sq_candidato", how="left")
        .join(total_paga, on="sq_candidato", how="left")
        .join(repasse_contratado, on="sq_candidato", how="left")
        .join(repasse_pago, on="sq_candidato", how="left")
        .with_columns(
            pl.when(tem_contas).then(pl.col(c).fill_null(0.0)).otherwise(None).alias(c)
            for c in _COLUNAS_DESPESA
        )
    )
    base = _corrigir(base, list(_COLUNAS_DESPESA), correcao)
    por_cand = financeiro.custo_por_voto(base).filter(pl.col("despesa_contratada").is_not_null())

    classificadas = financeiro.classificar_receitas(receitas)
    resumo_cand = {
        linha["sq_candidato"]: linha
        for linha in financeiro.resumo_receitas(classificadas).to_dicts()
    }
    resumo_rec = grupos.receitas_grupo(classificadas, sqs).to_dicts()[0]
    agg = financeiro.custo_por_voto_agregado(base).to_dicts()[0]
    soma = financeiro.custo_por_voto(
        por_cand.select(
            pl.col("despesa_contratada").sum(),
            pl.col("despesa_paga").sum(),
            pl.col("votos").sum(),
        )
    ).to_dicts()[0]
    por_sq = {c.sq_candidato: c for c in candidaturas}
    bases = BasesPorEscopo(repo)
    aptos_de = {sq: bases.de(c)[0] for sq, c in por_sq.items() if sq in com_contas}

    # Por candidato: receita bruta (o que ele recebeu), com despesa que inclui repasses (§4.8).
    cand = pl.DataFrame(
        [
            (
                linha["sq_candidato"],
                linha["votos"],
                resumo_cand.get(linha["sq_candidato"], {}).get("receita_total", 0.0),
                resumo_cand.get(linha["sq_candidato"], {}).get("receita_financeira", 0.0),
                aptos_de[linha["sq_candidato"]],
                linha["despesa_total_contratada"],
                linha["despesa_total_paga"],
            )
            for linha in por_cand.to_dicts()
        ],
        schema={
            "sq_candidato": pl.Int64,
            "votos": pl.Int64,
            "receita_total": pl.Float64,
            "receita_financeira": pl.Float64,
            "aptos": pl.Int64,
            "despesa_contratada": pl.Float64,
            "despesa_paga": pl.Float64,
        },
        orient="row",
    )
    cand = financeiro.saldo_campanha(
        financeiro.receita_por_mil_aptos(financeiro.receita_por_voto(cand))
    )
    metricas = {linha["sq_candidato"]: linha for linha in cand.to_dicts()}

    # Grupo: receita líquida de repasses internos — a mesma de `receitas.receita_total`.
    internos = {
        linha["sq_candidato"]: linha["internos"]
        for linha in classificadas.filter(
            financeiro.expr_repasse_candidato(classificadas)
            & pl.col("sq_candidato_doador").is_in(sqs)
        )
        .group_by("sq_candidato")
        .agg(pl.col("vr_receita").sum().alias("internos"))
        .to_dicts()
    }
    liquida = pl.DataFrame(
        [
            (
                sq,
                votos.get(sq, 0),
                resumo_cand.get(sq, {}).get("receita_total", 0.0) - internos.get(sq, 0.0)
                if sq in com_contas
                else None,
            )
            for sq in sqs
        ],
        schema={"sq_candidato": pl.Int64, "votos": pl.Int64, "receita_total": pl.Float64},
        orient="row",
    )
    por_voto_grupo = financeiro.receita_por_voto_agregado(liquida).to_dicts()[0]
    dist = financeiro.distribuicao_receita(liquida).to_dicts()[0]
    cargos = {c.ds_cargo for c in candidaturas if c.sq_candidato in com_contas}
    aptos_grupo: int | None = None
    mil_aptos: float | None = None
    if len(cargos) == 1:
        circunscricoes = {
            (c.ds_cargo, c.sg_uf): bases.de(c)[0]
            for c in candidaturas
            if c.sq_candidato in com_contas
        }
        aptos_grupo = sum(circunscricoes.values())
        mil_aptos = financeiro.receita_por_mil_aptos(
            pl.DataFrame({"receita_total": [resumo_rec["receita_total"]], "aptos": [aptos_grupo]})
        )["receita_por_mil_aptos"].item()
    saldo_grupo = SaldoGrupo(saldo_contratado=None, saldo_financeiro=None, pct_receita_gasta=None)
    if cand.height:
        saldo_grupo = SaldoGrupo(
            **financeiro.saldo_campanha(
                cand.select(
                    pl.col("receita_total").sum(),
                    pl.col("receita_financeira").sum(),
                    pl.col("despesa_contratada").sum(),
                    pl.col("despesa_paga").sum(),
                )
            )
            .select("saldo_contratado", "saldo_financeiro", "pct_receita_gasta")
            .to_dicts()[0]
        )
    desconhecido = resumo_rec["receita_repasses_doador_desconhecido"] or 0.0
    return ContasAgregadas(
        por_candidato=[
            ContasCand(
                candidatura=por_sq[linha["sq_candidato"]],
                custo=ResumoCustoCandidato(
                    despesa_contratada=linha["despesa_contratada"],
                    despesa_paga=linha["despesa_paga"],
                    divida=linha["divida"],
                    votos=linha["votos"],
                    custo_voto_contratado=linha["custo_voto_contratado"],
                    custo_voto_pago=linha["custo_voto_pago"],
                ),
                receita_total=resumo_cand.get(linha["sq_candidato"], {}).get("receita_total", 0.0),
                resumo=resumo_cand.get(linha["sq_candidato"], {}),
                receita_por_voto=metricas[linha["sq_candidato"]]["receita_por_voto"],
                receita_por_mil_aptos=metricas[linha["sq_candidato"]]["receita_por_mil_aptos"],
                saldo_contratado=metricas[linha["sq_candidato"]]["saldo_contratado"],
                saldo_financeiro=metricas[linha["sq_candidato"]]["saldo_financeiro"],
                pct_receita_gasta=metricas[linha["sq_candidato"]]["pct_receita_gasta"],
                repasses_contratados=linha["repasse_contratado"],
                repasses_pagos=linha["repasse_pago"],
            )
            for linha in por_cand.to_dicts()
        ],
        agregado=ResumoCustoGrupo(
            despesa_contratada=soma["despesa_contratada"],
            despesa_paga=soma["despesa_paga"],
            divida=soma["divida"],
            votos=soma["votos"],
            custo_voto_contratado=agg["custo_voto_contratado"],
            custo_voto_pago=agg["custo_voto_pago"],
            mediana_custo_voto_contratado=agg["mediana_custo_voto_contratado"],
            candidatos_sem_voto_excluidos=agg["candidatos_sem_voto_excluidos"],
        ),
        receitas=_receitas_out(resumo_rec, desconhecido),
        receita_por_voto=ReceitaPorVotoGrupo(**por_voto_grupo),
        distribuicao=DistribuicaoReceita(**dist),
        saldo=saldo_grupo,
        receita_por_mil_aptos=mil_aptos,
        aptos=aptos_grupo,
        parcial=repo.tp_prestacao_contas(ano).upper() == "PARCIAL",
        base_ipca=correcao[2] if correcao else None,
    )


def receitas_out(linha: dict[str, float | None]) -> ResumoReceitasOut:
    """`ResumoReceitasOut` de uma linha de `resumo_receitas` (candidato, sem campos do grupo)."""
    return _receitas_out(linha, None)


def _receitas_out(linha: dict[str, float | None], desconhecido: float | None) -> ResumoReceitasOut:
    """Converte a linha da lib; `desconhecido` não nulo marca o resumo como de grupo."""
    grupo = "receita_repasses_internos" in linha
    total = linha["receita_total"] or 0.0
    return ResumoReceitasOut(
        por_categoria={
            c: linha[f"receita_{c}"] or 0.0
            for c in financeiro.CATEGORIAS_RECEITA
            if linha[f"receita_{c}"]
        },
        receita_total=total,
        receita_financeira=linha["receita_financeira"] or 0.0,
        receita_estimavel=linha["receita_estimavel"] or 0.0,
        receita_repasses_candidatos=linha["receita_repasses_candidatos"] or 0.0,
        receita_sem_repasses=linha["receita_sem_repasses"] or 0.0,
        receita_repasses_internos=linha.get("receita_repasses_internos") if grupo else None,
        receita_repasses_doador_desconhecido=desconhecido if grupo else None,
        faixa_receita=FaixaReceita(minima=total - (desconhecido or 0.0), maxima=total)
        if grupo
        else None,
        pct_publico=linha["pct_publico"],
        pct_autofinanciamento=linha["pct_autofinanciamento"],
        pct_pessoa_fisica=linha["pct_pessoa_fisica"],
        pct_estimavel=linha["pct_estimavel"],
        hhi_fontes=linha["hhi_fontes"],
        n_efetivo_fontes=linha["n_efetivo_fontes"],
    )
