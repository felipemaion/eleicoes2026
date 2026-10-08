"""Conferência T-A04: números do processado + `indicadores` × fontes oficiais independentes.

Uso (a partir da raiz do repositório):

    uv run python packages/indicadores/scripts/conferir.py \\
        --processed data/processed --saida /tmp/conferencia

Fontes (rede só aqui; cache em --cache, padrão ~/.cache/eleicoes2026/conferencia):
- 2026: JSON de divulgação resultados.tse.jus.br/oficial/ele2026/<eleicao>/dados/<uf>/
  <uf>-c<cargo>-e<eleicao>-u.json — todas as UFs (Missão no país inteiro) + BR (presidente).
- 2022: cdn.tse.jus.br votacao_secao_2022_<UF>.zip e detalhe_votacao_secao_2022.zip, lidos em
  fluxo (sem descompactar em disco) e agregados do zero.

Saída: um CSV por bloco de comparação em --saida e `resumo.md` com as tabelas usadas em
docs/metodologia/conferencia.md. Código de saída 1 se alguma comparação não "confere" — a
explicação de cada caso fica no relatório, não no script.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import polars as pl
from indicadores import conferencia, desempenho

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)  # fmt: skip
AMOSTRA = ("SP", "RJ", "SC", "BA", "DF")
ELEICAO_2026 = {"federal": 6257, "estadual": 6259}
ELEICAO_2022 = {"federal": 544, "estadual": 546}
CARGOS_ESTADUAIS = (3, 5, 6, 7)  # DF: 8 no lugar de 7
NR_MISSAO = 14
URL_JSON = (
    "https://resultados.tse.jus.br/oficial/ele2026/{e}/dados/{uf}/{uf}-c{c:04d}-e{e:06d}-u.json"
)
URL_SECAO = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_{uf}.zip"
)
URL_DETALHE = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/"
    "detalhe_votacao_secao_2022.zip"
)
NULOS_TSE = ("#NULO", "#NE", "#NULO#")
BLOCO = 128 * 1024 * 1024
MEDIDAS_TOTAIS = [
    "aptos",
    "comparecimento",
    "votos_validos",
    "votos_nominais_validos",
    "votos_legenda",
    "votos_brancos",
    "votos_nulos",
]


# --------------------------------------------------------------------------- rede e cache


def baixar(url: str, destino: Path) -> Path:
    """Baixa `url` para `destino` se ainda não estiver no cache."""
    if destino.exists() and destino.stat().st_size:
        return destino
    if not url.startswith("https://"):
        raise ValueError(f"baixar: só https, recebi {url!r}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Esquema conferido acima (S310): só URLs https fixas do TSE.
    pedido = urllib.request.Request(url, headers={"User-Agent": "eleicoes2026-conferencia/1.0"})  # noqa: S310
    temporario = destino.with_suffix(destino.suffix + ".parcial")
    with urllib.request.urlopen(pedido, timeout=300) as resp, temporario.open("wb") as f:  # noqa: S310
        while bloco := resp.read(1 << 20):
            f.write(bloco)
    temporario.rename(destino)
    return destino


def json_2026(cache: Path, uf: str, cargo: int) -> dict[str, Any]:
    """JSON de divulgação de 2026 (UF × cargo; `uf="BR"` com cargo 1 para presidente)."""
    eleicao = ELEICAO_2026["federal" if cargo == 1 else "estadual"]
    url = URL_JSON.format(e=eleicao, uf=uf.lower(), c=cargo)
    caminho = baixar(url, cache / "divulgacao_2026" / Path(url).name)
    doc: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
    return doc


# --------------------------------------------------------------------------- leitura em fluxo


def _inteiros(df: pl.DataFrame) -> pl.DataFrame:
    """Nomes em minúsculas; colunas do TSE → Int64 (marcadores de nulo do TSE → null)."""
    df = df.rename(str.lower)
    return df.with_columns(
        pl.when(pl.col(c).is_in(NULOS_TSE)).then(None).otherwise(pl.col(c)).cast(pl.Int64).alias(c)
        for c in df.columns
    )


def agregar_csv_zip(
    zip_path: Path,
    membro: str,
    colunas: list[str],
    agregar: Callable[[pl.DataFrame], pl.DataFrame],
) -> pl.DataFrame:
    """Lê um CSV do TSE dentro do zip em blocos, aplica `agregar` (somas) e reagrega.

    Evita descompactar em disco (SP 2022 tem 5,4 GB descompactado).
    """
    parciais: list[pl.DataFrame] = []
    with zipfile.ZipFile(zip_path) as z, z.open(membro) as f:
        cabecalho = f.readline()
        resto = b""
        while True:
            bloco = f.read(BLOCO)
            dados = resto + bloco
            corte = dados.rfind(b"\n") + 1 if bloco else len(dados)
            parte, resto = dados[:corte], dados[corte:]
            if parte.strip():
                df = pl.read_csv(
                    io.BytesIO(cabecalho + parte),
                    separator=";",
                    columns=colunas,
                    infer_schema=False,
                    encoding="utf8-lossy",
                )
                parciais.append(agregar(_inteiros(df)))
            if not bloco:
                break
    junto = pl.concat(parciais)
    chaves = [c for c in junto.columns if not c.startswith("qt_")]
    return junto.group_by(chaves).agg(pl.col("^qt_.*$").sum()).sort(chaves)


def secao_2022(cache: Path, uf: str) -> pl.DataFrame:
    """Votos por votável (1º turno) agregados de `votacao_secao_2022_<UF>`; cache em Parquet."""
    destino = cache / "agregados" / f"votacao_secao_2022_{uf}.parquet"
    if destino.exists():
        return pl.read_parquet(destino)
    zip_path = baixar(
        URL_SECAO.format(uf=uf), cache / "votacao_secao" / f"votacao_secao_2022_{uf}.zip"
    )

    def agregar(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.filter(pl.col("nr_turno") == 1)
            .group_by("cd_eleicao", "cd_cargo", "nr_votavel", "sq_candidato")
            .agg(pl.col("qt_votos").sum())
        )

    colunas = ["NR_TURNO", "CD_ELEICAO", "CD_CARGO", "NR_VOTAVEL", "SQ_CANDIDATO", "QT_VOTOS"]
    df = agregar_csv_zip(zip_path, f"votacao_secao_2022_{uf}.csv", colunas, agregar)
    df = df.with_columns(pl.lit(uf).alias("sg_uf"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(destino)
    return df


def detalhe_secao_2022(cache: Path, uf: str) -> pl.DataFrame:
    """Totais por cargo (1º turno) agregados de `detalhe_votacao_secao_2022_<UF>`."""
    destino = cache / "agregados" / f"detalhe_votacao_secao_2022_{uf}.parquet"
    if destino.exists():
        return pl.read_parquet(destino)
    zip_path = baixar(
        URL_DETALHE, cache / "detalhe_votacao_secao" / "detalhe_votacao_secao_2022.zip"
    )
    medidas = [
        "QT_APTOS",
        "QT_COMPARECIMENTO",
        "QT_VOTOS_NOMINAIS",
        "QT_VOTOS_LEGENDA",
        "QT_VOTOS_BRANCOS",
        "QT_VOTOS_NULOS",
    ]

    def agregar(df: pl.DataFrame) -> pl.DataFrame:
        return (
            df.filter(pl.col("nr_turno") == 1)
            .group_by("cd_eleicao", "cd_cargo")
            .agg(pl.col("^qt_.*$").sum())
        )

    colunas = ["NR_TURNO", "CD_ELEICAO", "CD_CARGO", *medidas]
    df = agregar_csv_zip(zip_path, f"detalhe_votacao_secao_2022_{uf}.csv", colunas, agregar)
    df = df.with_columns(pl.lit(uf).alias("sg_uf"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(destino)
    return df


# --------------------------------------------------------------------------- nosso lado


def ler_processado(processed: Path, dataset: str, ano: int, ufs: Iterable[str]) -> pl.DataFrame:
    """Concatena os Parquet de `dataset`/`ano` das `ufs` (as que existirem)."""
    arquivos = [processed / dataset / f"ano={ano}" / f"{uf}.parquet" for uf in ufs]
    return pl.concat([pl.read_parquet(a) for a in arquivos if a.exists()], how="diagonal_relaxed")


def principais(df: pl.DataFrame, ano: int) -> pl.DataFrame:
    """1º turno das eleições gerais ordinárias (exclui suplementares, ex.: 6278 em 2022)."""
    codigos = list((ELEICAO_2026 if ano == 2026 else ELEICAO_2022).values())
    return df.filter((pl.col("nr_turno") == 1) & pl.col("cd_eleicao").is_in(codigos))


def nosso_totais(processed: Path, ano: int, ufs: Iterable[str]) -> pl.DataFrame:
    """Totais UF × cargo do `detalhe_votacao_munzona` (denominadores do painel)."""
    d = principais(ler_processado(processed, "detalhe_votacao_munzona", ano, ufs), ano)
    return (
        d.group_by("sg_uf", "cd_cargo")
        .agg(
            pl.col("qt_aptos").sum().alias("aptos"),
            pl.col("qt_comparecimento").sum().alias("comparecimento"),
            pl.col("qt_total_votos_validos").sum().alias("votos_validos"),
            pl.col("qt_votos_nominais_validos").sum().alias("votos_nominais_validos"),
            pl.col("qt_total_votos_leg_validos").sum().alias("votos_legenda"),
            pl.col("qt_votos_brancos").sum().alias("votos_brancos"),
            pl.col("qt_total_votos_nulos").sum().alias("votos_nulos"),
            # Brutos (antes da destinação), para a conferência por seção de 2022.
            (
                pl.col("qt_votos_nominais_validos")
                + pl.col("qt_votos_nom_convr_leg_validos")
                + pl.col("qt_votos_nominais_anulados")
                + pl.col("qt_votos_nominais_anul_subjud")
            )
            .sum()
            .alias("votos_nominais_brutos"),
            (
                pl.col("qt_votos_leg_validos")
                + pl.col("qt_votos_legenda_anulados")
                + pl.col("qt_votos_legenda_anul_subjud")
            )
            .sum()
            .alias("votos_legenda_brutos"),
        )
        .with_columns(pl.col("cd_cargo").cast(pl.Int64))
    )


def nosso_candidatos(processed: Path, ano: int, ufs: Iterable[str]) -> pl.DataFrame:
    """Votos por candidato via `desempenho.votos_nominais` (a função que o painel usa)."""
    v = principais(ler_processado(processed, "votacao_candidato_munzona", ano, ufs), ano)
    chaves = ("sg_uf", "cd_cargo", "sq_candidato", "nr_partido")
    return desempenho.votos_nominais(v, chaves=chaves).with_columns(
        (
            pl.col("votos_nominais_validos")
            + pl.col("votos_anulados")
            + pl.col("votos_convertidos_legenda")
        ).alias("votos_apurados"),
        pl.col("cd_cargo").cast(pl.Int64),
        pl.col("nr_partido").cast(pl.Int64),
    )


def nosso_partidos(processed: Path, ano: int, ufs: Iterable[str]) -> pl.DataFrame:
    """Legenda por partido do `votacao_partido_munzona` (total válido e bruto)."""
    p = principais(ler_processado(processed, "votacao_partido_munzona", ano, ufs), ano)
    return (
        p.group_by("sg_uf", "cd_cargo", "nr_partido")
        .agg(
            (pl.col("qt_votos_legenda_validos") + pl.col("qt_votos_nom_convr_leg_validos"))
            .sum()
            .alias("votos_legenda"),
            (
                pl.col("qt_votos_legenda_validos")
                + pl.col("qt_votos_legenda_anulados")
                + pl.col("qt_votos_legenda_anul_subjud")
            )
            .sum()
            .alias("votos_legenda_brutos"),
        )
        .with_columns(pl.col("cd_cargo").cast(pl.Int64), pl.col("nr_partido").cast(pl.Int64))
    )


# --------------------------------------------------------------------------- blocos 2026


def cargos_da_uf(uf: str) -> list[int]:
    """Cargos estaduais disputados na UF (DF elege distrital, não estadual)."""
    return [8 if (c == 7 and uf == "DF") else c for c in CARGOS_ESTADUAIS]


def _validos_da_fonte(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("votos").alias("votos_apurados"),
        pl.when(pl.col("destinacao") == "Válido")
        .then(pl.col("votos"))
        .otherwise(0)
        .alias("votos_nominais_validos"),
    )


def blocos_2026(processed: Path, cache: Path) -> dict[str, pl.DataFrame]:
    """Compara 2026 com o JSON de divulgação (todas as UFs + presidente BR)."""
    docs = [json_2026(cache, uf, c) for uf in UFS for c in cargos_da_uf(uf)]
    br = json_2026(cache, "BR", 1)
    f_totais = pl.concat([conferencia.divulgacao_totais(d) for d in docs])
    f_cand = _validos_da_fonte(pl.concat([conferencia.divulgacao_candidatos(d) for d in docs]))
    f_part = pl.concat([conferencia.divulgacao_partidos(d) for d in docs])

    blocos: dict[str, pl.DataFrame] = {}
    chaves_uf = ["sg_uf", "cd_cargo"]
    # Presidente fica na partição BR.parquet do processado (layout do TSE), não nas UFs.
    nosso_t = nosso_totais(processed, 2026, [*UFS, "BR"])
    blocos["2026_totais_uf_cargo"] = conferencia.comparar(
        nosso_t.filter(pl.col("cd_cargo") != 1).select(*chaves_uf, *MEDIDAS_TOTAIS),
        f_totais.select(*chaves_uf, *MEDIDAS_TOTAIS),
        chaves_uf,
    )
    # Presidente: total Brasil (UFs + exterior ZZ, todos em BR.parquet) — detecta dupla
    # contagem de aptos.
    nosso_br = (
        nosso_t.filter(pl.col("cd_cargo") == 1)
        .select(pl.col(m).sum() for m in MEDIDAS_TOTAIS)
        .select(pl.lit("BR").alias("sg_uf"), pl.lit(1, pl.Int64).alias("cd_cargo"), pl.all())
    )
    blocos["2026_totais_br_presidente"] = conferencia.comparar(
        nosso_br,
        conferencia.divulgacao_totais(br).select(*chaves_uf, *MEDIDAS_TOTAIS),
        chaves_uf,
    )

    chaves_c = ["sg_uf", "cd_cargo", "sq_candidato"]
    medidas_c = ["votos_apurados", "votos_nominais_validos"]
    nc_todos = nosso_candidatos(processed, 2026, [*UFS, "BR"])
    nc = nc_todos.filter(pl.col("cd_cargo") != 1)
    blocos["2026_candidatos_todos"] = conferencia.comparar(
        nc.select(*chaves_c, *medidas_c), f_cand.select(*chaves_c, *medidas_c), chaves_c
    )
    nc_pres = (
        nc_todos.filter((pl.col("cd_cargo") == 1) & (pl.col("nr_partido") == NR_MISSAO))
        .group_by("cd_cargo", "sq_candidato", "nr_partido")
        .agg(pl.col(*medidas_c).sum())
        .with_columns(pl.lit("BR").alias("sg_uf"))
    )
    fc_pres = _validos_da_fonte(conferencia.divulgacao_candidatos(br)).filter(
        pl.col("nr_partido") == NR_MISSAO
    )
    missao_nosso = pl.concat(
        [
            nc.filter(pl.col("nr_partido") == NR_MISSAO).select(*chaves_c, *medidas_c),
            nc_pres.select(*chaves_c, *medidas_c),
        ]
    )
    missao_fonte = pl.concat(
        [
            f_cand.filter(pl.col("nr_partido") == NR_MISSAO).select(*chaves_c, *medidas_c),
            fc_pres.select(*chaves_c, *medidas_c),
        ]
    )

    def por_cargo(df: pl.DataFrame) -> pl.DataFrame:
        return df.group_by("cd_cargo").agg(
            pl.len().cast(pl.Int64).alias("n_candidaturas"), pl.col(*medidas_c).sum()
        )

    blocos["2026_missao_por_cargo"] = conferencia.comparar(
        por_cargo(missao_nosso), por_cargo(missao_fonte), ["cd_cargo"]
    )
    blocos["2026_missao_candidatos"] = conferencia.comparar(missao_nosso, missao_fonte, chaves_c)

    chaves_p = ["sg_uf", "cd_cargo", "nr_partido"]
    prop = pl.col("cd_cargo").is_in(conferencia.CARGOS_PROPORCIONAIS)
    blocos["2026_legenda_partidos"] = conferencia.comparar(
        nosso_partidos(processed, 2026, UFS).filter(prop).select(*chaves_p, "votos_legenda"),
        f_part.filter(prop).select(*chaves_p, "votos_legenda"),
        chaves_p,
    )
    return blocos


# --------------------------------------------------------------------------- blocos 2022


def mbl_2022(raiz: Path) -> pl.DataFrame:
    """Lista de referência do grupo MBL 2022 (sem CPF)."""
    with (raiz / "data" / "reference" / "mbl_2022.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return pl.DataFrame(
        {
            "nome": [r["nome"] for r in linhas],
            "sg_uf": [r["uf"] for r in linhas],
            "sq_candidato": [int(r["sq_candidato"]) for r in linhas],
        }
    )


def inaptos_2022(processed: Path, ufs: Iterable[str]) -> list[int]:
    """`sq_candidato` com candidatura INAPTA (`consulta_cand`) — para checar os omitidos."""
    cand = ler_processado(processed, "consulta_cand", 2022, ufs)
    return cand.filter(pl.col("ds_situacao_candidatura") == "INAPTO")["sq_candidato"].to_list()


def blocos_2022(processed: Path, cache: Path, raiz: Path) -> dict[str, pl.DataFrame]:
    """Compara 2022 com `votacao_secao` + `detalhe_votacao_secao` agregados do zero.

    Duas regras da totalização que a seção não aplica, reconciliadas à parte (bloco
    `2022_reconciliacao_nulos`): voto em candidato INAPTO e legenda de partido sem registro
    válido vão a **nulo** (CE art. 175 §3º) e o TSE omite esses votáveis do `*_munzona`. E o
    `detalhe_votacao_munzona` de 2022 soma os nominais convertidos em legenda ora em
    `qt_votos_nom_convr_leg_validos`, ora em `qt_votos_leg_validos` (SP) — por isso o total
    compara nominais + legenda juntos; a legenda por partido é conferida no bloco próprio.
    """
    mbl = mbl_2022(raiz)
    ufs_secao = sorted({*AMOSTRA, *mbl["sg_uf"].to_list()})
    codigos = list(ELEICAO_2022.values())
    na_amostra = pl.col("sg_uf").is_in(AMOSTRA)
    blocos: dict[str, pl.DataFrame] = {}

    sec = conferencia.classificar_votavel(
        pl.concat([secao_2022(cache, uf) for uf in ufs_secao]).filter(
            pl.col("cd_eleicao").is_in(codigos)
        )
    )
    chaves_c = ["sg_uf", "cd_cargo", "sq_candidato"]
    chaves_p = ["sg_uf", "cd_cargo", "nr_partido"]
    chaves_uf = ["sg_uf", "cd_cargo"]
    nc = nosso_candidatos(processed, 2022, ufs_secao).select(*chaves_c, "votos_apurados")
    prop = pl.col("cd_cargo").is_in(conferencia.CARGOS_PROPORCIONAIS)
    np_ = nosso_partidos(processed, 2022, AMOSTRA).filter(prop)

    fonte_c = (
        sec.filter(pl.col("tipo_votavel") == "nominal")
        .group_by(*chaves_c)
        .agg(pl.col("qt_votos").sum().alias("votos_apurados"))
    )
    # Votável da seção ausente do *_munzona = omitido pelo TSE (voto foi a nulo).
    omitidos = fonte_c.join(nc.select(chaves_c), on=chaves_c, how="anti")
    sq_inaptos = inaptos_2022(processed, ufs_secao)
    blocos["2022_omitidos_sao_inaptos"] = conferencia.comparar(
        omitidos.group_by("sg_uf").agg(pl.len().cast(pl.Int64).alias("n_omitidos")),
        omitidos.filter(pl.col("sq_candidato").is_in(sq_inaptos))
        .group_by("sg_uf")
        .agg(pl.len().cast(pl.Int64).alias("n_omitidos")),
        ["sg_uf"],
    )
    inaptos = pl.col("sq_candidato").is_in(omitidos["sq_candidato"].to_list())
    fonte_p = (
        sec.filter((pl.col("tipo_votavel") == "legenda") & na_amostra)
        .group_by("sg_uf", "cd_cargo", pl.col("nr_votavel").alias("nr_partido"))
        .agg(pl.col("qt_votos").sum().alias("votos_legenda_brutos"))
    )
    legenda_sem_registro = fonte_p.join(np_.select(chaves_p), on=chaves_p, how="anti")
    anulados_na_totalizacao = (
        pl.concat(
            [
                fonte_c.filter(inaptos & na_amostra).select(
                    *chaves_uf, pl.col("votos_apurados").alias("votos")
                ),
                legenda_sem_registro.select(
                    *chaves_uf, pl.col("votos_legenda_brutos").alias("votos")
                ),
            ]
        )
        .group_by(chaves_uf)
        .agg(pl.col("votos").sum())
    )

    det = pl.concat([detalhe_secao_2022(cache, uf) for uf in AMOSTRA]).filter(
        pl.col("cd_eleicao").is_in(codigos)
    )
    fonte_t = det.group_by(chaves_uf).agg(
        pl.col("qt_aptos").sum().alias("aptos"),
        pl.col("qt_comparecimento").sum().alias("comparecimento"),
        (pl.col("qt_votos_nominais") + pl.col("qt_votos_legenda"))
        .sum()
        .alias("votos_nominais_e_legenda_brutos"),
        pl.col("qt_votos_brancos").sum().alias("votos_brancos"),
        pl.col("qt_votos_nulos").sum().alias("votos_nulos_digitados"),
    )
    nosso_t = nosso_totais(processed, 2022, AMOSTRA).with_columns(
        (pl.col("votos_nominais_brutos") + pl.col("votos_legenda_brutos")).alias(
            "votos_nominais_e_legenda_brutos"
        )
    )
    # Totais: o que vai a nulo na totalização volta para "nominais e legenda" do nosso lado.
    ajustado = nosso_t.join(anulados_na_totalizacao, on=chaves_uf, how="left").with_columns(
        pl.col("votos").fill_null(0)
    )
    medidas = ["aptos", "comparecimento", "votos_nominais_e_legenda_brutos", "votos_brancos"]
    blocos["2022_totais_uf_cargo"] = conferencia.comparar(
        ajustado.with_columns(pl.col("votos_nominais_e_legenda_brutos") + pl.col("votos")).select(
            *chaves_uf, *medidas
        ),
        fonte_t.select(*chaves_uf, *medidas),
        chaves_uf,
    )
    # Reconciliação: nulos do nosso − nulos digitados na seção = votos em inaptos + legenda
    # de partido sem registro (somados da seção).
    blocos["2022_reconciliacao_nulos"] = conferencia.comparar(
        nosso_t.join(fonte_t, on=chaves_uf).select(
            *chaves_uf,
            (pl.col("votos_nulos") - pl.col("votos_nulos_digitados")).alias(
                "votos_que_viraram_nulos"
            ),
        ),
        ajustado.select(*chaves_uf, pl.col("votos").alias("votos_que_viraram_nulos")),
        chaves_uf,
    )

    blocos["2022_candidatos_todos"] = conferencia.comparar(
        nc.filter(na_amostra), fonte_c.filter(na_amostra & ~inaptos), chaves_c
    )
    do_mbl = pl.col("sq_candidato").is_in(mbl["sq_candidato"].to_list())
    blocos["2022_mbl_candidatos"] = conferencia.comparar(
        nc.filter(do_mbl), fonte_c.filter(do_mbl & ~inaptos), chaves_c
    )
    blocos["2022_legenda_partidos"] = conferencia.comparar(
        np_.select(*chaves_p, "votos_legenda_brutos"),
        fonte_p.join(legenda_sem_registro.select(chaves_p), on=chaves_p, how="anti"),
        chaves_p,
    )
    return blocos


# --------------------------------------------------------------------------- relatório


def resumo(blocos: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Uma linha por bloco: comparações, quantas conferem/divergem e a maior |diferença|."""
    linhas = []
    for nome, df in blocos.items():
        n = dict(df["situacao"].value_counts().iter_rows())
        linhas.append(
            {
                "bloco": nome,
                "comparacoes": df.height,
                "confere": n.get("confere", 0),
                "diverge": n.get("diverge", 0),
                "so_nosso": n.get("so_nosso", 0),
                "so_fonte": n.get("so_fonte", 0),
                "max_abs_dif": df["diferenca"].abs().max(),
            }
        )
    return pl.DataFrame(linhas)


def _celula(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:,.0f}" if v.is_integer() else f"{v:,.4f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def markdown(df: pl.DataFrame) -> str:
    """Tabela markdown simples (milhar com vírgula, como o TSE não usa — só para leitura)."""
    linhas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * df.width]
    linhas += ["| " + " | ".join(_celula(v) for v in r) + " |" for r in df.rows()]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    """Roda os blocos pedidos, grava CSVs e `resumo.md` em --saida."""
    raiz = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--processed", type=Path, default=raiz / "data" / "processed")
    ap.add_argument(
        "--cache", type=Path, default=Path.home() / ".cache" / "eleicoes2026" / "conferencia"
    )
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--anos", default="2022,2026")
    a = ap.parse_args(argv)
    anos = {int(x) for x in a.anos.split(",")}

    blocos: dict[str, pl.DataFrame] = {}
    if 2026 in anos:
        blocos |= blocos_2026(a.processed, a.cache)
    if 2022 in anos:
        blocos |= blocos_2022(a.processed, a.cache, raiz)

    a.saida.mkdir(parents=True, exist_ok=True)
    partes = []
    for nome, df in blocos.items():
        df.write_csv(a.saida / f"{nome}.csv")
        fora = df.filter(pl.col("situacao") != "confere")
        partes.append(f"## {nome}\n\n{df.height} comparações; fora de 'confere': {fora.height}\n")
        if fora.height:
            partes.append(markdown(fora.head(40)) + "\n")
    r = resumo(blocos)
    texto = "# Conferência T-A04 — resumo\n\n" + markdown(r) + "\n\n" + "\n".join(partes)
    (a.saida / "resumo.md").write_text(texto, encoding="utf-8")
    print(texto)
    nao_confere = r.select(pl.col("diverge", "so_nosso", "so_fonte").sum()).sum_horizontal()
    return 1 if nao_confere.item() else 0


if __name__ == "__main__":
    sys.exit(main())
