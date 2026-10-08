"""Cadastro de redes sociais do TSE → ``redes_candidatos`` (ADR 0008).

Fonte oficial: ``consulta_cand/rede_social_candidato_AAAA.zip`` — uma linha por URL/texto que o
candidato declarou (``NR_ORDEM_REDE_SOCIAL`` 1…n). Só os candidatos dos grupos pedidos (padrão
``missao_2026`` e ``mbl_2026``) entram; o username vem de :func:`etl.redes.url.username_instagram`
e o que não for perfil é contado, não adivinhado.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from contratos import CONTRATOS, validar

from etl.redes.url import username_instagram
from etl.tse_csv import membros_dados, scan_texto, transcodificar

REDE = "instagram"
GRUPOS_PADRAO = ("missao_2026", "mbl_2026")
PREFIXO = "rede_social_candidato"
CT = CONTRATOS["redes_candidatos"]


class ErroRedes(RuntimeError):  # noqa: N818 - nome de domínio
    """Arquivo ausente ou configuração de grupo que o ETL não sabe resolver."""


def sqs_do_grupo(raiz_processed: Path, repo: Path, ano: int, grupo: str) -> set[int]:
    """``sq_candidato`` do grupo em ``config/grupos.yaml`` (partido OU lista; sem ``filtro``)."""
    config = yaml.safe_load((repo / "config/grupos.yaml").read_text(encoding="utf-8"))
    if grupo not in config["grupos"]:
        raise ErroRedes(f"grupo {grupo!r} não existe em config/grupos.yaml")
    criterio: dict[str, Any] = config["grupos"][grupo]["criterio"]
    desconhecidos = set(criterio) - {"partido", "lista"}
    if desconhecidos or "filtro" in criterio.get("lista", {}):
        raise ErroRedes(f"grupo {grupo!r}: critério {sorted(desconhecidos)} não suportado")
    sqs: set[int] = set()
    if "partido" in criterio:
        arquivos = sorted((raiz_processed / "consulta_cand" / f"ano={ano}").glob("*.parquet"))
        if not arquivos:
            raise ErroRedes(f"sem consulta_cand de {ano} em {raiz_processed} — rode o ETL antes")
        partido = pl.scan_parquet(arquivos).filter(pl.col("nr_partido") == criterio["partido"])
        sqs |= set(partido.select("sq_candidato").collect()["sq_candidato"].to_list())
    if "lista" in criterio:
        lista = pl.read_csv(repo / criterio["lista"]["arquivo"], infer_schema=False)
        coluna = lista[criterio["lista"]["coluna"]].drop_nulls().cast(pl.Int64)
        sqs |= set(coluna.to_list())
    return sqs


def _ler_declaracoes(zip_path: Path) -> pl.DataFrame:
    """Todas as linhas do cadastro (UFs + BR; ``_BRASIL`` é a união e duplicaria)."""
    partes: list[pl.DataFrame] = []
    with tempfile.TemporaryDirectory() as tmp:
        for membro in membros_dados(zip_path, PREFIXO):
            csv = transcodificar(zip_path, membro, Path(tmp) / f"{Path(membro).stem}.csv")
            partes.append(
                scan_texto(csv)
                .select(
                    pl.col("SQ_CANDIDATO").cast(pl.Int64).alias("sq_candidato"),
                    pl.col("NR_ORDEM_REDE_SOCIAL").cast(pl.Int32).alias("nr_ordem"),
                    pl.col("DS_URL").str.strip_chars().alias("url_tse"),
                    pl.col("DT_GERACAO").str.to_date("%d/%m/%Y").alias("dt_geracao"),
                    pl.col("AA_ELEICAO").cast(pl.Int16).alias("ano_eleicao"),
                )
                .collect()
            )
    if not partes:
        raise ErroRedes(f"{zip_path}: nenhum CSV {PREFIXO}_AAAA_UF.csv")
    return pl.concat(partes)


def processar_redes_tse(
    ano: int,
    raiz_raw: Path,
    raiz_processed: Path,
    *,
    repo: Path,
    grupos: tuple[str, ...] = GRUPOS_PADRAO,
) -> dict[str, int]:
    """Grava ``redes_candidatos/ano=<ano>/redes_candidatos.parquet`` e devolve contagens."""
    zip_path = raiz_raw / "tse" / PREFIXO / f"{PREFIXO}_{ano}.zip"
    if not zip_path.exists():
        raise ErroRedes(f"{zip_path} não existe — rode `etl baixar --fonte {PREFIXO}` antes")
    sqs: set[int] = set()
    for grupo in grupos:
        sqs |= sqs_do_grupo(raiz_processed, repo, ano, grupo)
    declaracoes = _ler_declaracoes(zip_path).filter(pl.col("sq_candidato").is_in(sqs))
    # Só linhas que citam Instagram entram na contagem de rejeitadas (Facebook etc. são esperados)
    cita = pl.col("url_tse").str.to_lowercase().str.contains(r"instagra[mn]|^\s*@")
    declaracoes = declaracoes.with_columns(
        pl.col("url_tse").map_elements(username_instagram, return_dtype=pl.Utf8).alias("username")
    )
    validas = declaracoes.filter(pl.col("username").is_not_null()).sort("sq_candidato", "nr_ordem")
    # o mesmo perfil pode aparecer em duas linhas do cadastro: vale a de menor ordem
    distintos = validas.unique(
        subset=["sq_candidato", "username"], keep="first", maintain_order=True
    )
    por_candidato = distintos.group_by("sq_candidato").agg(pl.len().alias("n_perfis"))
    saida = distintos.with_columns(
        pl.lit(REDE).alias("rede"),
        (pl.col("nr_ordem") == pl.col("nr_ordem").min().over("sq_candidato")).alias("principal"),
    ).select(list(CT.colunas))
    validar(saida, CT)
    destino = raiz_processed / "redes_candidatos" / f"ano={ano}" / "redes_candidatos.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    saida.write_parquet(destino)
    return {
        "candidatos_no_grupo": len(sqs),
        "com_instagram": por_candidato.height,
        "sem_instagram": len(sqs) - por_candidato.height,
        "perfis": saida.height,
        "com_mais_de_um_perfil": int((por_candidato["n_perfis"] > 1).sum()),
        "urls_instagram_rejeitadas": declaracoes.filter(cita & pl.col("username").is_null()).height,
    }
