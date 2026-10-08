"""Indicadores espaciais (spec §3): LQ, HHI/N efetivo, dominância de Ames, índice G,
tipologia de Ames, n baixo, suavização bayesiana empírica, Moran/LISA e agregação H3.

Notação (uma entidade *c*, um cargo, uma UF): `v_ci` votos de *c* na unidade *i*;
`V_c = Σ_i v_ci`; `v_i` válidos do cargo em *i*; `V = Σ_i v_i`; `s_i = v_ci / V_c`;
`x_i = aptos_i / Σ aptos`.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from indicadores._comum import (
    LIMIAR_N_BAIXO,
    exigir_colunas,
    exigir_unicidade,
    expr_penetracao,
    razao,
    sobre,
)

SEMENTE_PERMUTACAO = 20261004
"""Semente fixa das permutações de Moran/LISA (spec §3.6) — resultados reprodutíveis."""

LIMIAR_COBERTURA_H3_PCT = 5.0
"""% de votos sem coordenada acima do qual a camada H3 do município ganha alerta (spec §1.2)."""


def n_baixo(
    df: pl.DataFrame,
    coluna_aptos: str = "aptos",
    coluna_taxa: str = "taxa_referencia",
    limiar: float = LIMIAR_N_BAIXO,
) -> pl.DataFrame:
    """Acrescenta `esperado = aptos × taxa_referencia` e `n_baixo = esperado < 20` (spec §1.4).

    `taxa_referencia` é a taxa (proporção) do mesmo candidato/grupo na UF. Esperado nulo
    (taxa indefinida) também conta como n baixo. Critério NCHS/CDC: menos de 20 eventos →
    erro-padrão relativo ≳ 23 %.
    """
    exigir_colunas(df, [coluna_aptos, coluna_taxa], "n_baixo")
    esperado = pl.col(coluna_aptos).cast(pl.Float64) * pl.col(coluna_taxa)
    return df.with_columns(esperado.alias("esperado")).with_columns(
        (pl.col("esperado").is_null() | (pl.col("esperado") < limiar)).alias("n_baixo")
    )


def lq(tabela: pl.DataFrame, entidade: str = "sq_candidato") -> pl.DataFrame:
    """Acrescenta o quociente locacional `lq = (v_ci / V_c) / (v_i / V)` (spec §3.1).

    `LQ > 1`: a entidade é mais forte na unidade do que na UF. `V_c = 0` ou `v_i = 0` → `null`.
    Ref.: Silva & Davidian (2013), *BPSR* 7(2).

    Args:
        tabela: saída de `desempenho.montar_tabela` (todas as unidades da UF por entidade).
    """
    exigir_colunas(tabela, [entidade, "votos", "validos"], "lq")
    total_entidade = sobre(pl.col("votos").sum(), [entidade])
    total_validos = sobre(pl.col("validos").sum(), [entidade])
    return tabela.with_columns(
        razao(
            pl.col("votos").cast(pl.Float64) * total_validos,
            total_entidade.cast(pl.Float64) * pl.col("validos"),
        ).alias("lq")
    )


def concentracao(tabela: pl.DataFrame, entidade: str = "sq_candidato") -> pl.DataFrame:
    """HHI, N efetivo, dominância de Ames e índice G por entidade (spec §3.2).

    - `hhi = Σ_i s_i²` (Herfindahl–Hirschman entre unidades);
    - `n_efetivo_municipios = 1 / HHI` (Laakso & Taagepera 1979);
    - `dominancia_ames = Σ_i s_i · (v_ci / v_i)` (Ames 1995);
    - `indice_g = Σ_i (s_i − x_i)²` (G bruto de Ellison–Glaeser adaptado ao voto por
      Avelino, Biderman & Silva 2011).

    `V_c = 0` → todos `null`; `Σ aptos = 0` → `indice_g` nulo.

    Args:
        tabela: saída de `desempenho.montar_tabela` (todas as unidades da UF por entidade).
    """
    exigir_colunas(tabela, [entidade, "votos", "aptos", "validos"], "concentracao")
    s = razao(pl.col("votos"), sobre(pl.col("votos").sum(), [entidade]))
    x = razao(pl.col("aptos"), sobre(pl.col("aptos").sum(), [entidade]))
    fatia_local = razao(pl.col("votos"), pl.col("validos")).fill_null(0.0)
    somas = (
        tabela.with_columns(s.alias("_s"), x.alias("_x"), fatia_local.alias("_f"))
        .group_by(entidade)
        .agg(
            pl.col("votos").sum(),
            pl.col("aptos").sum().alias("_aptos"),
            (pl.col("_s") ** 2).sum().alias("hhi"),
            (pl.col("_s") * pl.col("_f")).sum().alias("dominancia_ames"),
            ((pl.col("_s") - pl.col("_x")) ** 2).sum().alias("indice_g"),
        )
    )
    tem_voto = pl.col("votos") > 0
    nulo = pl.lit(None, dtype=pl.Float64)
    return (
        somas.with_columns(
            pl.when(tem_voto).then(pl.col("hhi")).otherwise(nulo).alias("hhi"),
            pl.when(tem_voto).then(pl.col("dominancia_ames")).otherwise(nulo),
            pl.when(tem_voto & (pl.col("_aptos") > 0)).then(pl.col("indice_g")).otherwise(nulo),
        )
        .with_columns(razao(pl.lit(1.0), pl.col("hhi")).alias("n_efetivo_municipios"))
        .select(entidade, "votos", "hhi", "n_efetivo_municipios", "dominancia_ames", "indice_g")
        .sort(entidade)
    )


def tipologia_ames(
    candidatos: pl.DataFrame, quociente_eleitoral: int, entidade: str = "sq_candidato"
) -> pl.DataFrame:
    """Tipologia de Ames por concentração (G) × dominância (D) (spec §3.3, decisão 1.7).

    Corte = mediana de G e de D entre as candidaturas do cargo × UF (todos os partidos) com
    `votos ≥ 0,10 × QE` (piso do CE art. 108, Lei 14.211/2021). `G > med` → concentrado,
    `D > med` → dominante (estrito: empate vai para baixo). Candidatos abaixo do piso recebem
    tipo com `na_populacao_referencia = false`. Sem população de referência → medianas e
    tipos nulos. Ref.: Ames (1995), *AJPS* 39(2).

    Args:
        candidatos: `entidade`, `votos`, `indice_g`, `dominancia_ames` de **todos** os
            candidatos do cargo × UF (saída de `concentracao`).
        quociente_eleitoral: QE do cargo × UF.

    Raises:
        ValueError: QE ≤ 0 ou coluna ausente.
    """
    if quociente_eleitoral <= 0:
        raise ValueError(f"quociente eleitoral inválido para a tipologia: {quociente_eleitoral}")
    exigir_colunas(candidatos, [entidade, "votos", "indice_g", "dominancia_ames"], "tipologia")
    limiar = 0.10 * quociente_eleitoral
    g, d = pl.col("indice_g"), pl.col("dominancia_ames")
    na_ref = (pl.col("votos") >= limiar) & g.is_not_null() & d.is_not_null()
    return (
        candidatos.with_columns(
            pl.lit(limiar).alias("limiar_votos"),
            g.filter(na_ref).median().alias("mediana_g"),
            d.filter(na_ref).median().alias("mediana_dominancia"),
            na_ref.alias("na_populacao_referencia"),
        )
        .with_columns(
            pl.concat_str(
                pl.when(g > pl.col("mediana_g"))
                .then(pl.lit("concentrado"))
                .when(g <= pl.col("mediana_g"))
                .then(pl.lit("disperso")),
                pl.when(d > pl.col("mediana_dominancia"))
                .then(pl.lit("dominante"))
                .when(d <= pl.col("mediana_dominancia"))
                .then(pl.lit("compartilhado")),
                separator="-",
            ).alias("tipo")
        )
        .select(
            entidade,
            "limiar_votos",
            "mediana_g",
            "mediana_dominancia",
            "tipo",
            "na_populacao_referencia",
        )
    )


def suavizacao_eb(
    df: pl.DataFrame,
    eventos: str = "votos",
    base: str = "aptos",
    por: Sequence[str] = (),
) -> pl.DataFrame:
    """Suavização bayesiana empírica global de Marshall (1991), estimador por momentos (§3.5).

    Com `r_i = v_i / n_i`: `b = Σv / Σn`; `s² = Σ n_i (r_i − b)² / Σn`;
    `a = max(s² − b / n̄, 0)`; `w_i = a / (a + b / n_i)`; `θ_i = w_i r_i + (1 − w_i) b`.
    Unidades com `n = 0` ficam fora. Prior por grupo `por` (ex.: candidato; a UF é implícita
    no recorte). Saída em proporção: colunas `taxa_bruta`, `peso`, `taxa_eb`, `eb_a`, `eb_b`.
    Ref.: Marshall, R. J. (1991), *Applied Statistics* 40(2): 283–294 (= "EB rate" do GeoDa).
    """
    exigir_colunas(df, [eventos, base, *por], "suavizacao_eb")
    v, n = pl.col(eventos).cast(pl.Float64), pl.col(base).cast(pl.Float64)
    soma_n = sobre(n.sum(), por)
    return (
        df.filter(pl.col(base) > 0)
        .with_columns((v / n).alias("taxa_bruta"), (sobre(v.sum(), por) / soma_n).alias("eb_b"))
        .with_columns(
            (
                sobre((n * (pl.col("taxa_bruta") - pl.col("eb_b")) ** 2).sum(), por) / soma_n
                - pl.col("eb_b") / sobre(n.mean(), por)
            )
            .clip(lower_bound=0.0)
            .alias("eb_a")
        )
        .with_columns(
            # a = 0 e b = 0 (nenhum voto): peso indefinido; tudo encolhe para b = 0.
            razao(pl.col("eb_a"), pl.col("eb_a") + pl.col("eb_b") / n).fill_null(0.0).alias("peso")
        )
        .with_columns(
            (pl.col("peso") * pl.col("taxa_bruta") + (1 - pl.col("peso")) * pl.col("eb_b")).alias(
                "taxa_eb"
            )
        )
    )


@dataclass(frozen=True)
class ResultadoMoran:
    """Moran global e LISA. `locais`: `id, valor, lisa, quadrante, pseudo_p` por unidade."""

    moran_i: float | None
    pseudo_p: float | None
    locais: pl.DataFrame


def _vizinhos(ids: list[object], vizinhanca: pl.DataFrame) -> list[list[int]]:
    posicao = {u: i for i, u in enumerate(ids)}
    conjuntos: list[set[int]] = [set() for _ in ids]
    for origem, destino in vizinhanca.select("id", "vizinho").iter_rows():
        if origem not in posicao or destino not in posicao:
            raise ValueError(f"moran_lisa: id desconhecido na vizinhança ({origem}, {destino})")
        if origem != destino:
            conjuntos[posicao[origem]].add(posicao[destino])
    ilhas = [ids[i] for i, viz in enumerate(conjuntos) if not viz]
    if ilhas:
        raise ValueError(
            f"moran_lisa: unidades sem vizinho {ilhas[:10]} — atribua o vizinho mais próximo "
            "(k = 1) antes (spec §3.6)"
        )
    return [sorted(viz) for viz in conjuntos]


def _moran_global(z: list[float], vizinhos: list[list[int]], soma_z2: float) -> float:
    # W padronizada por linha → S0 = n, e I = Σ z_i·lag_i / Σ z².
    lag = (sum(z[j] for j in viz) / len(viz) for viz in vizinhos)
    return sum(zi * li for zi, li in zip(z, lag, strict=True)) / soma_z2


def _extremo(observado: float, permutado: float, referencia: float) -> bool:
    return permutado >= observado if observado >= referencia else permutado <= observado


def moran_lisa(
    valores: pl.DataFrame,
    vizinhanca: pl.DataFrame,
    permutacoes: int = 999,
    semente: int = SEMENTE_PERMUTACAO,
) -> ResultadoMoran:
    """Moran global (Moran 1950) e LISA (Anselin 1995) com W padronizada por linha (§3.6).

    `z_i = y_i − ȳ`; `lag_i = média dos z_j vizinhos`; `I = Σ z_i lag_i / Σ z²`;
    `I_i = z_i · lag_i / m₂`, `m₂ = Σ z² / n`. Quadrante pelo sinal de `z_i` e de `lag_i`
    (`> 0` → "alto"; zero conta como "baixo"). Pseudo-p por permutação: global com permutação
    total; local condicional (mantém `z_i`, sorteia os vizinhos entre os demais), ambos
    `(M + 1) / (P + 1)` na cauda do sinal observado, semente fixa. Variância zero → tudo nulo.

    Args:
        valores: `id`, `valor` (use a penetração EB, nunca absolutos).
        vizinhanca: arestas `id → vizinho` (contiguidade rainha; ilhas com k = 1).
        permutacoes: 0 desliga a inferência (`pseudo_p` nulo).

    Raises:
        ValueError: valor nulo, id repetido, id desconhecido ou unidade sem vizinho.
    """
    exigir_colunas(valores, ["id", "valor"], "moran_lisa(valores)")
    exigir_colunas(vizinhanca, ["id", "vizinho"], "moran_lisa(vizinhanca)")
    exigir_unicidade(valores, ["id"], "moran_lisa(valores)")
    if valores["valor"].null_count():
        raise ValueError("moran_lisa: valores nulos — suavize ou exclua antes")
    ids: list[object] = valores["id"].to_list()
    vizinhos = _vizinhos(ids, vizinhanca)
    y = valores["valor"].cast(pl.Float64).to_list()
    n = len(y)
    media = sum(y) / n
    z = [v - media for v in y]
    soma_z2 = sum(zi * zi for zi in z)
    base = valores.select("id", "valor")
    if soma_z2 == 0.0:
        nulos = pl.lit(None, dtype=pl.Float64)
        return ResultadoMoran(
            None,
            None,
            base.with_columns(
                nulos.alias("lisa"),
                pl.lit(None, dtype=pl.String).alias("quadrante"),
                nulos.alias("pseudo_p"),
            ),
        )
    m2 = soma_z2 / n
    lag = [sum(z[j] for j in viz) / len(viz) for viz in vizinhos]
    lisa = [zi * li / m2 for zi, li in zip(z, lag, strict=True)]
    quadrante = [
        f"{'alto' if zi > 0 else 'baixo'}-{'alto' if li > 0 else 'baixo'}"
        for zi, li in zip(z, lag, strict=True)
    ]
    moran_i = _moran_global(z, vizinhos, soma_z2)

    p_global: float | None = None
    p_local: list[float | None] = [None] * n
    if permutacoes > 0:
        rng = random.Random(semente)  # noqa: S311 - permutação reprodutível, não cripto
        esperado_i = -1.0 / (n - 1) if n > 1 else 0.0
        embaralhado = z[:]
        extremos = 0
        for _ in range(permutacoes):
            rng.shuffle(embaralhado)
            extremos += _extremo(moran_i, _moran_global(embaralhado, vizinhos, soma_z2), esperado_i)
        p_global = (extremos + 1) / (permutacoes + 1)
        for i, viz in enumerate(vizinhos):
            outros = z[:i] + z[i + 1 :]
            k = len(viz)
            extremos = 0
            for _ in range(permutacoes):
                lag_p = sum(rng.sample(outros, k)) / k
                extremos += _extremo(lisa[i], z[i] * lag_p / m2, 0.0)
            p_local[i] = (extremos + 1) / (permutacoes + 1)

    locais = base.with_columns(
        pl.Series("lisa", lisa, dtype=pl.Float64),
        pl.Series("quadrante", quadrante, dtype=pl.String),
        pl.Series("pseudo_p", p_local, dtype=pl.Float64),
    )
    return ResultadoMoran(moran_i, p_global, locais)


def agregar_h3(locais: pl.DataFrame, coluna_h3: str, por: Sequence[str] = ()) -> pl.DataFrame:
    """Agrega locais de votação em células H3 e recalcula a penetração (spec §1.2, §3.7).

    Soma `aptos` e `votos` por célula (nunca média de taxas); locais sem coordenada
    (`coluna_h3` nula) ficam fora do H3. `n_baixo` usa como taxa de referência a penetração
    da entidade sobre **todos** os locais recebidos (inclusive sem coordenada) — passe todos
    os locais da UF. Resolução menor: passe a coluna do pai (`cell_to_parent`) já calculada.

    Saída: `por…, h3, aptos, votos, taxa_referencia, penetracao, esperado, n_baixo`.
    """
    exigir_colunas(locais, [*por, coluna_h3, "aptos", "votos"], "agregar_h3")
    referencia = razao(sobre(pl.col("votos").sum(), por), sobre(pl.col("aptos").sum(), por))
    celulas = (
        locais.with_columns(referencia.alias("taxa_referencia"))
        .filter(pl.col(coluna_h3).is_not_null())
        .group_by([*por, coluna_h3])
        .agg(pl.col("aptos").sum(), pl.col("votos").sum(), pl.col("taxa_referencia").first())
        .rename({coluna_h3: "h3"})
        .with_columns(expr_penetracao().alias("penetracao"))
        .sort([*por, "h3"])
    )
    return n_baixo(celulas)


def cobertura_h3(
    locais: pl.DataFrame,
    coluna_h3: str = "h3_r8",
    por: Sequence[str] = (),
    limiar_pct: float = LIMIAR_COBERTURA_H3_PCT,
) -> pl.DataFrame:
    """Por município: `votos`, `pct_votos_sem_coordenada` e `alerta_cobertura_h3` (spec §1.2).

    Alerta quando mais de `limiar_pct` % dos votos vêm de locais sem coordenada válida.
    Município sem votos → percentual e alerta nulos.
    """
    exigir_colunas(locais, [*por, "cd_mun_ibge", coluna_h3, "votos"], "cobertura_h3")
    return (
        locais.group_by([*por, "cd_mun_ibge"])
        .agg(
            pl.col("votos").sum(),
            pl.col("votos").filter(pl.col(coluna_h3).is_null()).sum().alias("_sem"),
        )
        .with_columns(
            (100 * razao(pl.col("_sem"), pl.col("votos"))).alias("pct_votos_sem_coordenada")
        )
        .with_columns(
            (pl.col("pct_votos_sem_coordenada") > limiar_pct).alias("alerta_cobertura_h3")
        )
        .drop("_sem")
        .sort([*por, "cd_mun_ibge"])
    )
