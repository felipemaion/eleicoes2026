"""Tabela ``municipios``: crosswalk TSE↔IBGE + área oficial + AMC.

AMC (Área Mínima Comparável) 2022↔2026: município criado depois de 2022 é agregado ao(s)
município(s) de origem. O IBGE só publica AMC censitária (até 2010), então a lista abaixo é
manual e verificada contra o crosswalk: `ErroMunicipios` se algum código sumir.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from contratos import CONTRATOS, validar


class ErroMunicipios(ValueError):  # noqa: N818 - nome de domínio
    """Dado de município inconsistente (código ausente, sem área...)."""


@dataclass(frozen=True)
class AgregacaoAmc:
    """Município novo (``nova``) e os de ``origens`` de onde saiu território."""

    nova: int
    origens: tuple[int, ...]
    fonte: str


AGREGACOES_AMC: tuple[AgregacaoAmc, ...] = (
    # Boa Esperança do Norte/MT: Lei MT 7.264/2000, desmembrada de Sorriso e Nova Ubiratã;
    # validada pelo STF (out/2023) e incluída pelo IBGE na DTB 2024 (5.569 municípios).
    # Não existia na eleição de 2022 (votava em Sorriso/Nova Ubiratã); confirmado:
    # é o único código de 2026 ausente em 2022 no eleitorado_local_votacao.
    AgregacaoAmc(
        nova=5101837,
        origens=(5107925, 5106240),
        fonte="https://www.al.mt.gov.br/storage/webdisco/leis/lei-7264-2000.pdf",
    ),
)


def limpar_areas(bruto: pl.DataFrame) -> pl.DataFrame:
    """Planilha de áreas do IBGE → ``cd_mun_ibge``, ``area_km2``.

    Descarta o rodapé (sem código) e as "Áreas Operacionais" das lagoas (RS, 43000xx),
    que não são municípios.
    """
    col_area = next(c for c in bruto.columns if c.startswith("AR_MUN_"))
    return (
        bruto.filter(pl.col("CD_MUN").is_not_null())
        .select(
            pl.col("CD_MUN").cast(pl.Int32).alias("cd_mun_ibge"),
            pl.col(col_area).cast(pl.Float64).alias("area_km2"),
        )
        .filter(~pl.col("cd_mun_ibge").is_between(4300000, 4300009))
    )


def ler_areas(xls: Path) -> pl.DataFrame:
    """Lê a aba ``AR_BR_MUN_*`` do XLS de áreas territoriais do IBGE."""
    import fastexcel

    aba = next(a for a in fastexcel.read_excel(str(xls)).sheet_names if a.startswith("AR_BR_MUN"))
    return limpar_areas(pl.read_excel(xls, sheet_name=aba))


def calcular_amc(
    codigos: Iterable[int], agregacoes: Iterable[AgregacaoAmc] = AGREGACOES_AMC
) -> dict[int, int]:
    """``cd_mun_ibge → cd_amc``. O código da AMC é o menor do grupo (determinístico)."""
    conhecidos = set(codigos)
    amc = {c: c for c in conhecidos}
    for ag in agregacoes:
        grupo = {ag.nova, *ag.origens}
        faltam = sorted(grupo - conhecidos)
        if faltam:
            raise ErroMunicipios(f"AMC cita município(s) inexistente(s): {faltam}")
        raiz = min(grupo)
        for c in grupo:
            amc[c] = raiz
    return amc


def montar_municipios(crosswalk: pl.DataFrame, areas: pl.DataFrame) -> pl.DataFrame:
    """Junta crosswalk + área + AMC e valida o contrato; falha alto se faltar área."""
    sem_area = sorted(set(crosswalk["cd_mun_ibge"].to_list()) - set(areas["cd_mun_ibge"].to_list()))
    if sem_area:
        raise ErroMunicipios(f"município(s) sem área oficial: {sem_area}")
    amc = calcular_amc(crosswalk["cd_mun_ibge"].to_list())
    out = (
        crosswalk.join(areas, on="cd_mun_ibge", how="inner")
        .with_columns(
            pl.col("cd_mun_ibge").replace_strict(amc, return_dtype=pl.Int32).alias("cd_amc")
        )
        .select(
            "cd_mun_ibge",
            pl.col("cd_municipio_tse").alias("cd_mun_tse"),
            "sg_uf",
            pl.col("nm_municipio_ibge").alias("nm_municipio"),
            "area_km2",
            "cd_amc",
        )
        .sort("cd_mun_ibge")
    )
    validar(out, CONTRATOS["municipios"])
    return out
