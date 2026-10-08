"""Leitura dos CSV do TSE: o único lugar que conhece encoding, nulos, decimal e datas.

Os arquivos são Latin-1, separados por ``;``, com texto entre aspas. O polars não lê Latin-1
em streaming, então cada membro do ZIP é transcodificado em pedaços para UTF-8 num arquivo
temporário e lido por ``scan_csv`` (tudo como texto; a conversão de tipos é explícita).
"""

from __future__ import annotations

import itertools
import re
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from contratos import Contrato

CHUNK = 8 * 1024 * 1024
# Texto: marcadores de "sem valor" do TSE.
NULOS_TEXTO = ("#NULO", "#NE", "#NI")
# Numéricos/códigos: -1, -3 e -4 são sentinelas (contagens e códigos nunca são negativos).
# Latitude/longitude são negativas no Brasil, por isso `dec` só anula os marcadores de texto.
NULOS_INTEIROS = ("-1", "-3", "-4")


def membros_dados(zip_path: Path, prefixo: str | None = None) -> list[str]:
    """CSVs a processar: um por UF e o ``_BR`` (presidente). ``_BRASIL`` é a união dos dois
    (conferido: 39.982 = 27.416 + 12.566 linhas em ``detalhe_votacao_munzona_2022``) e
    duplicaria tudo se lido junto.

    ZIPs com vários datasets (prestação de contas) usam ``prefixo``: só entram
    ``<prefixo>_AAAA_UF.csv`` (o prefixo ``receitas_candidatos`` não pega
    ``receitas_candidatos_doador_originario_*``)."""
    padrao = re.compile(rf"{re.escape(prefixo)}_\d{{4}}_[A-Z]{{2}}\.csv") if prefixo else None
    with zipfile.ZipFile(zip_path) as z:
        return sorted(
            n
            for n in z.namelist()
            if n.lower().endswith(".csv")
            and not n.endswith("_BRASIL.csv")
            and (padrao is None or padrao.fullmatch(n))
        )


def transcodificar(zip_path: Path, membro: str, destino: Path) -> Path:
    """Latin-1 → UTF-8, em pedaços (os arquivos têm centenas de MB)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z, z.open(membro) as src, destino.open("wb") as dst:
        while pedaco := src.read(CHUNK):
            dst.write(pedaco.decode("latin-1").encode("utf-8"))  # Latin-1 é 1 byte/char: sem corte
    return destino


BLOCO_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class Bloco:
    """Pedaço de um CSV grande, em UTF-8 e com cabeçalho; ``linhas`` conta só as de dados."""

    caminho: Path
    linhas: int


def blocos_utf8(
    zip_path: Path, membro: str, tmp: Path, bloco_bytes: int = BLOCO_BYTES
) -> Iterator[Bloco]:
    """Lê o membro do ZIP em blocos de ~``bloco_bytes`` sem materializar o CSV inteiro.

    O ``votacao_secao`` de SP passa de 10 GB descompactado; o disco do ETL não comporta uma
    cópia UTF-8 dessa. Cada bloco termina em quebra de linha, repete o cabeçalho e é apagado
    quando o consumidor pede o próximo. ``Bloco.linhas`` vem da contagem de ``\\n`` no fluxo,
    independente do parser, para o total de controle de linhas. Arquivo só com cabeçalho
    não rende bloco algum.
    """
    tmp.mkdir(parents=True, exist_ok=True)
    stem = Path(membro).stem
    with zipfile.ZipFile(zip_path) as z, z.open(membro) as src:
        cab = src.readline().decode("latin-1").encode("utf-8")
        pendente = b""
        for i in itertools.count():
            caminho = tmp / f"{stem}.{i:05d}.csv"
            linhas = escritos = 0
            try:
                with caminho.open("wb") as f:
                    f.write(cab)
                    while escritos < bloco_bytes:
                        pedaco = src.read(min(CHUNK, bloco_bytes))
                        dados = pendente + pedaco
                        if pedaco:  # só escreve linhas completas; o resto vai para o próximo
                            corte = dados.rfind(b"\n") + 1
                            dados, pendente = dados[:corte], dados[corte:]
                        else:
                            pendente = b""
                            if dados and not dados.endswith(b"\n"):
                                dados += b"\n"
                        f.write(dados.decode("latin-1").encode("utf-8"))
                        escritos += len(dados)
                        linhas += dados.count(b"\n")
                        if not pedaco:
                            break
                if linhas:
                    yield Bloco(caminho, linhas)
            finally:
                caminho.unlink(missing_ok=True)
            if not pedaco:
                return


def _expr(origem: str, tipo: pl.DataType | type[pl.DataType]) -> pl.Expr:
    texto = pl.col(origem).str.strip_chars()
    if tipo == pl.Utf8:
        return pl.when(texto.is_in(NULOS_TEXTO)).then(None).otherwise(pl.col(origem))
    if tipo == pl.Date:
        validos = texto.is_in(NULOS_TEXTO) | (texto == "")
        return pl.when(validos).then(None).otherwise(texto).str.to_date("%d/%m/%Y", strict=True)
    if tipo == pl.Float64:
        validos = texto.is_in(NULOS_TEXTO) | (texto == "")
        return (
            pl.when(validos)
            .then(None)
            .otherwise(texto.str.replace(",", "."))
            .cast(pl.Float64, strict=True)
        )
    nulo = texto.is_in((*NULOS_TEXTO, *NULOS_INTEIROS)) | (texto == "")
    return pl.when(nulo).then(None).otherwise(texto).cast(tipo, strict=True)


def scan_texto(csv: Path) -> pl.LazyFrame:
    """CSV UTF-8 já transcodificado, tudo como texto (sem inferência nem conversão)."""
    return pl.scan_csv(
        csv,
        separator=";",
        quote_char='"',
        infer_schema=False,
        encoding="utf8",
        truncate_ragged_lines=False,
    )


def ler_membro(
    zip_path: Path,
    membro: str,
    contrato: Contrato,
    tmp: Path,
    extras: Sequence[str] = (),
) -> pl.LazyFrame:
    """Transcodifica o membro para ``tmp`` e devolve :func:`ler_csv`."""
    csv = transcodificar(zip_path, membro, tmp / (Path(membro).stem + ".utf8.csv"))
    return ler_csv(csv, membro, contrato, extras)


def ler_csv(
    csv: Path,
    membro: str,
    contrato: Contrato,
    extras: Sequence[str] = (),
) -> pl.LazyFrame:
    """LazyFrame tipado de um CSV UTF-8, com as colunas lidas conforme ``contrato``.

    Colunas derivadas (``contrato.derivadas``) não existem na origem e ficam de fora.
    ``extras`` são colunas brutas (texto) adicionais, minúsculas, p.ex. CPF para o hash.
    Coluna ausente na origem ou valor que não converte → erro (nada de fallback silencioso).
    """
    lf = scan_texto(csv)
    presentes = set(lf.collect_schema().names())
    exprs: list[pl.Expr] = []
    for nome, tipo in contrato.colunas.items():
        if nome in contrato.derivadas:
            continue
        origem = contrato.origem.get(nome, nome.upper())
        if origem not in presentes:
            raise pl.exceptions.ColumnNotFoundError(f"{membro}: coluna {origem} ausente")
        exprs.append(_expr(origem, tipo).alias(nome))
    for extra in extras:
        exprs.append(pl.col(extra.upper()).alias(extra))
    return lf.select(exprs)
