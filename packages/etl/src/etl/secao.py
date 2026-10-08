"""Votação por seção → local de votação → H3 (T-D05).

O ``votacao_secao`` do TSE tem uma linha por seção × candidato (SP 2022: dezenas de milhões).
Aqui ele é lido em blocos (``tse_csv.blocos_utf8``) e agregado já na leitura para o **local de
votação**, que é a menor unidade com coordenada (``eleitorado_local_votacao``). Saem três
datasets: ``votos_local`` (candidato × local × cargo), ``totais_local`` (nominais, legenda,
brancos e nulos por local × cargo) e ``locais_h3`` (local com coordenada → células H3).

Um Parquet só é publicado depois de passar no contrato e nos totais de controle: votos contra
o texto do CSV, linhas contra o fluxo e cada candidato contra o ``votacao_candidato_munzona``.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import h3  # type: ignore[import-untyped]  # h3 4.x não publica stubs
import polars as pl
from contratos import CONTRATOS, Contrato, validar

from etl.fontes.catalogo import alvos
from etl.manifesto import Manifesto
from etl.processar import ErroProcessamento, _conferir_municipios, _crosswalk
from etl.tse_csv import BLOCO_BYTES, blocos_utf8, ler_csv, scan_texto

LOG = logging.getLogger(__name__)
FONTE = "votacao_secao"
BRANCO, NULO = 95, 96  # NR_VOTAVEL reservado do TSE
RES_H3 = (8, 7, 6)  # ADR 0007: 8 canônica; 7 e 6 para a comparação 2022×2026
ALERTA_SEM_COORDENADA = 0.05  # spec: alerta quando > 5% dos votos ficam sem coordenada

VOTOS = CONTRATOS["votos_local"]
TOTAIS = CONTRATOS["totais_local"]
LOCAIS = CONTRATOS["locais_h3"]
LEITURA = CONTRATOS["votacao_secao"]
_LOCAL = ["ano_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona", "nr_local"]
_CHAVE_LOCAL = ["cd_municipio_tse", "nr_zona", "nr_local"]
Stats = dict[str, Any]


def _parcial(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Agrega um bloco (1º turno) em ``votos_local`` e ``totais_local`` parciais.

    Linha com ``sq_candidato`` nulo (o TSE grava -1/-3) não é candidato: 95/96 são brancos e
    nulos; o resto é voto de legenda.
    """
    df = df.rename({"nr_local_votacao": "nr_local"})
    votos = (
        df.filter(pl.col("sq_candidato").is_not_null())
        .group_by([*_LOCAL, "cd_cargo", "sq_candidato"])
        .agg(pl.col("qt_votos").sum().alias("votos"), pl.col("dt_geracao").max())
    )
    sem_cand = pl.col("sq_candidato").is_null()

    def soma(cond: pl.Expr, nome: str) -> pl.Expr:
        return pl.col("qt_votos").filter(cond).sum().alias(nome)

    totais = df.group_by([*_LOCAL, "cd_cargo"]).agg(
        soma(~sem_cand, "votos_nominais"),
        soma(sem_cand & ~pl.col("nr_votavel").is_in([BRANCO, NULO]), "votos_legenda"),
        soma(sem_cand & (pl.col("nr_votavel") == BRANCO), "votos_brancos"),
        soma(sem_cand & (pl.col("nr_votavel") == NULO), "votos_nulos"),
        pl.col("dt_geracao").max(),
    )  # fmt: skip
    return votos, totais


def _soma_texto(caminho: Path) -> int:
    """Σ QT_VOTOS do 1º turno lida do texto cru, sem passar pelo parser tipado."""
    v = (
        scan_texto(caminho)
        .filter(pl.col("NR_TURNO").str.strip_chars() == "1")
        .select(pl.col("QT_VOTOS").str.strip_chars().cast(pl.Int64, strict=False).sum())
        .collect()
        .item()
    )
    return int(v or 0)


def _consolidar(parciais: list[Path], chaves: list[str], valores: list[str]) -> pl.LazyFrame:
    """Soma os parciais dos blocos: um local pode ter sido cortado entre dois blocos."""
    return (
        pl.scan_parquet(parciais)
        .group_by(chaves)
        .agg(*[pl.col(c).sum() for c in valores], pl.col("dt_geracao").max())
    )


def _ligar_ibge(lf: pl.LazyFrame, cross: pl.LazyFrame, ct: Contrato) -> pl.LazyFrame:
    lf = lf.join(cross, on="cd_municipio_tse", how="left")
    return lf.select(list(ct.colunas)).sort(list(ct.chave))


def _conferir_munzona(votos: pl.LazyFrame, ano: int, nome_uf: str, raiz_proc: Path) -> Stats:
    """Σ votos por candidato × cargo = ``qt_votos_nominais`` do munzona (1º turno).

    O arquivo por seção também traz candidaturas ausentes do munzona (votos anulados, p.ex.
    indeferidas): são contadas em ``votos_fora_do_munzona`` e explicadas no handoff, mas um
    candidato que está nos dois e diverge é erro.
    """
    arq = raiz_proc / "votacao_candidato_munzona" / f"ano={ano}" / f"{nome_uf}.parquet"
    if not arq.exists():
        raise ErroProcessamento(
            f"{arq} não existe: processe `votacao_candidato_munzona` antes (total de controle)"
        )
    mz = (
        pl.scan_parquet(arq)
        .filter(pl.col("nr_turno") == 1)
        .group_by("sq_candidato", "cd_cargo")
        .agg(pl.col("qt_votos_nominais").sum().alias("munzona"))
    )
    sec = votos.group_by("sq_candidato", "cd_cargo").agg(pl.col("votos").sum().alias("secao"))
    j = mz.join(sec, on=["sq_candidato", "cd_cargo"], how="full", coalesce=True).collect()
    ruim = j.filter(
        pl.col("munzona").is_not_null() & (pl.col("munzona") != pl.col("secao").fill_null(0))
    )
    if ruim.height:
        raise ErroProcessamento(
            f"{nome_uf}: {ruim.height} candidato(s) com votos por local ≠ munzona, ex.: "
            f"{ruim.head(3).rows()} (sq_candidato, cd_cargo, munzona, secao)"
        )
    extra = j.filter(pl.col("munzona").is_null())
    return {
        "candidatos_fora_do_munzona": extra.height,
        "votos_fora_do_munzona": int(extra["secao"].sum() or 0),
    }


def _ler_blocos(
    zip_path: Path, membro: str, tmp: Path, bloco_bytes: int
) -> tuple[Stats, list[Path], list[Path], int]:
    """Lê o ZIP em blocos; grava parciais em ``tmp``; confere linhas bloco a bloco."""
    stats: Stats = {"linhas_origem": 0, "linhas_turno2_ignoradas": 0, "blocos": 0}
    pv: list[Path] = []
    pt: list[Path] = []
    texto = 0
    for i, bloco in enumerate(blocos_utf8(zip_path, membro, tmp / "csv", bloco_bytes)):
        df = ler_csv(bloco.caminho, membro, LEITURA).collect()
        if df.height != bloco.linhas:
            raise ErroProcessamento(
                f"{membro}: bloco {i} tem {df.height} linhas lidas × {bloco.linhas} no fluxo "
                "(quebra de linha dentro de campo?)"
            )
        texto += _soma_texto(bloco.caminho)
        turno1 = df.filter(pl.col("nr_turno") == 1)
        stats["linhas_origem"] += df.height
        stats["linhas_turno2_ignoradas"] += df.height - turno1.height
        stats["blocos"] += 1
        votos, totais = _parcial(turno1)
        for lista, parte, nome in ((pv, votos, "v"), (pt, totais, "t")):
            caminho = tmp / f"{nome}{i:05d}.parquet"
            parte.write_parquet(caminho)
            lista.append(caminho)
    return stats, pv, pt, texto


def _processar_uf(
    zip_path: Path, ano: int, nome_uf: str, cross: pl.LazyFrame, raiz_proc: Path, bloco_bytes: int
) -> Stats:
    """Um ZIP (UF, BR ou ZZ): lê em blocos, agrega, valida e só então publica os Parquets."""
    membro = f"{FONTE}_{ano}_{nome_uf}.csv"
    tmp = Path(tempfile.mkdtemp(prefix="etl-secao-"))
    try:
        stats, pv, pt, texto = _ler_blocos(zip_path, membro, tmp, bloco_bytes)
        if not pv:
            LOG.warning("%s: sem linhas de dados; nada a gravar", membro)
            return stats

        votos_lf = _consolidar(pv, [*_LOCAL, "cd_cargo", "sq_candidato"], ["votos"])
        totais_lf = _consolidar(
            pt, [*_LOCAL, "cd_cargo"],
            ["votos_nominais", "votos_legenda", "votos_brancos", "votos_nulos"],
        )  # fmt: skip
        pronto: dict[str, tuple[Path, Path, pl.LazyFrame]] = {}
        for lf, ct in ((votos_lf, VOTOS), (totais_lf, TOTAIS)):
            temporario = tmp / f"{ct.nome}.parquet"
            _ligar_ibge(lf, cross, ct).sink_parquet(temporario)
            saida = pl.scan_parquet(temporario)
            validar(saida, ct)
            _conferir_municipios(saida, membro)
            destino = raiz_proc / ct.nome / f"ano={ano}" / f"{nome_uf}.parquet"
            pronto[ct.nome] = (temporario, destino, saida)

        votos_saida, totais_saida = pronto["votos_local"][2], pronto["totais_local"][2]
        t = totais_saida.select(
            pl.col("votos_nominais").sum().alias("nominais"),
            (pl.col("votos_nominais") + pl.col("votos_legenda")
             + pl.col("votos_brancos") + pl.col("votos_nulos")).sum().alias("todos"),
        ).collect().row(0, named=True)  # fmt: skip
        nominais = int(votos_saida.select(pl.col("votos").sum()).collect().item())
        if t["todos"] != texto or t["nominais"] != nominais:
            raise ErroProcessamento(
                f"{membro}: totais de controle divergem: texto {texto}; totais_local "
                f"{t['todos']} (nominais {t['nominais']}); votos_local {nominais}"
            )
        stats |= {"votos_nominais": nominais, "votos_total": texto}
        stats |= _conferir_munzona(votos_saida, ano, nome_uf, raiz_proc)
        stats["dt_geracao"] = votos_saida.select(pl.col("dt_geracao").max()).collect().item()

        for temporario, destino, _ in pronto.values():  # só aqui, com tudo validado
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporario, destino)
        return stats
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def construir_locais_h3(ano: int, raiz_proc: Path) -> Stats:
    """``locais_h3`` do ano: locais do 1º turno com coordenada válida → H3 res 8/7/6.

    A coordenada vem do ``eleitorado_local_votacao`` (que já anula os pares inválidos e o
    exterior). Local sem coordenada **não** vai para o H3 (nem para o centróide do município,
    ADR 0007); devolve quantos locais e quantos votos nominais isso deixou de fora, por UF.
    """
    pasta = raiz_proc / "eleitorado_local_votacao" / f"ano={ano}"
    if not list(pasta.glob("*.parquet")):
        raise ErroProcessamento(f"{pasta} vazio: processe `eleitorado_local_votacao` antes")
    cadastro = (
        pl.scan_parquet(pasta / "*.parquet")
        .filter(pl.col("nr_turno") == 1)
        .select(
            pl.col("aa_eleicao").alias("ano_eleicao"),
            "nr_turno",
            "sg_uf",
            "cd_municipio_tse",
            "cd_mun_ibge",
            "nr_zona",
            pl.col("nr_local_votacao").alias("nr_local"),
            pl.col("nr_latitude").alias("lat"),
            pl.col("nr_longitude").alias("lon"),
            pl.col("qt_eleitor_secao").alias("aptos"),
            "dt_geracao",
        )
        .collect()
    )
    com = cadastro.filter(pl.col("lat").is_not_null() & pl.col("lon").is_not_null())
    r8, r7, r6 = RES_H3
    celulas = [h3.latlng_to_cell(la, lo, r8) for la, lo in zip(com["lat"], com["lon"], strict=True)]
    com = com.with_columns(
        h3=pl.Series(celulas, dtype=pl.Utf8),
        h3_r7=pl.Series([h3.cell_to_parent(c, r7) for c in celulas], dtype=pl.Utf8),
        h3_r6=pl.Series([h3.cell_to_parent(c, r6) for c in celulas], dtype=pl.Utf8),
    )
    saida = com.select(list(LOCAIS.colunas)).sort(list(LOCAIS.chave))
    validar(saida, LOCAIS)
    destino = raiz_proc / "locais_h3" / f"ano={ano}" / "locais_h3.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    saida.write_parquet(tmp)
    os.replace(tmp, destino)
    return _cobertura(ano, raiz_proc, cadastro, saida)


def _cobertura(ano: int, raiz_proc: Path, cadastro: pl.DataFrame, com_h3: pl.DataFrame) -> Stats:
    """Locais e votos nominais sem coordenada, no total e por UF do voto."""
    stats: Stats = {
        "locais": cadastro.height,
        "locais_com_h3": com_h3.height,
        "locais_sem_coordenada": cadastro.height - com_h3.height,
        "votos_sem_coordenada": 0,
        "votos_sem_cadastro": 0,
        "pct_votos_sem_coordenada": 0.0,
        "por_uf": {},
    }
    arqs = sorted((raiz_proc / "votos_local" / f"ano={ano}").glob("*.parquet"))
    if not arqs:
        return stats
    tem_h3 = com_h3.lazy().select(_CHAVE_LOCAL).with_columns(tem_h3=True)
    cadastrado = cadastro.lazy().select(_CHAVE_LOCAL).with_columns(cadastrado=True)
    votos = (
        pl.scan_parquet(arqs)
        .group_by("sg_uf", *_CHAVE_LOCAL)
        .agg(pl.col("votos").sum())
        .join(tem_h3, on=_CHAVE_LOCAL, how="left")
        .join(cadastrado, on=_CHAVE_LOCAL, how="left")
        .with_columns(pl.col("tem_h3").fill_null(False), pl.col("cadastrado").fill_null(False))
        .group_by("sg_uf")
        .agg(
            pl.col("votos").sum().alias("total"),
            pl.col("votos").filter(~pl.col("tem_h3")).sum().alias("sem"),
            pl.col("votos").filter(~pl.col("cadastrado")).sum().alias("sem_cadastro"),
        )
        .sort("sg_uf")
        .collect()
    )
    total, sem = int(votos["total"].sum()), int(votos["sem"].sum())
    stats |= {
        "votos_sem_coordenada": sem,
        "votos_sem_cadastro": int(votos["sem_cadastro"].sum()),
        "pct_votos_sem_coordenada": sem / total if total else 0.0,
        "por_uf": {
            r["sg_uf"]: round(r["sem"] / r["total"], 4)
            for r in votos.iter_rows(named=True)
            if r["total"]
        },
    }
    return stats


def processar_secao(
    ano: int,
    raiz_raw: Path,
    raiz_proc: Path,
    *,
    ufs: list[str] | None = None,
    manifesto: Manifesto | None = None,
    descartar_zip: bool = False,
    bloco_bytes: int = BLOCO_BYTES,
) -> Stats:
    """Processa ``votacao_secao`` de ``ano`` (todas as UFs do catálogo ou só ``ufs``).

    ``descartar_zip`` apaga cada ZIP depois de validado e publicado: o disco local não
    comporta os ~8 GB brutos dos dois anos; o sha256 continua no manifesto e o arquivo pode
    ser baixado de novo. Devolve os totais para o handoff (inclui ``por_uf``).
    """
    cross = _crosswalk(raiz_raw, raiz_proc, ano)
    por_uf: dict[str, Stats] = {}
    for alvo in alvos(ano, [FONTE]):
        nome_uf = alvo.destino.rsplit("_", 1)[1].removesuffix(".zip")
        if ufs and nome_uf not in ufs:
            continue
        zip_path = raiz_raw / alvo.destino
        if not zip_path.exists():
            raise ErroProcessamento(f"{zip_path} não existe; rode `etl baixar` antes")
        por_uf[nome_uf] = _processar_uf(zip_path, ano, nome_uf, cross, raiz_proc, bloco_bytes)
        dt = por_uf[nome_uf].get("dt_geracao")
        entrada = manifesto.por_caminho(alvo.destino) if manifesto and dt else None
        if manifesto and entrada and dt:
            manifesto.registrar(replace(entrada, dt_geracao=dt.isoformat()))
        if descartar_zip:
            zip_path.unlink()
    chaves = (
        "linhas_origem", "linhas_turno2_ignoradas", "blocos", "votos_nominais",
        "votos_fora_do_munzona", "candidatos_fora_do_munzona",
    )  # fmt: skip
    total: Stats = {k: sum(s.get(k, 0) for s in por_uf.values()) for k in chaves}
    total["ufs"] = por_uf
    return total | construir_locais_h3(ano, raiz_proc)
