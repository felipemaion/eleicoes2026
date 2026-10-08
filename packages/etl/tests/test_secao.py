"""Votação por seção → local de votação → H3, sobre a fixture real (Bujari e Capixaba, 2022).

O oráculo é o módulo ``csv`` lendo o ZIP de origem, independente do parser do ETL.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import h3  # type: ignore[import-untyped]  # h3 4.x não publica stubs
import polars as pl
import pytest
from contratos import CONTRATOS, validar
from etl.processar import ErroProcessamento, processar_fonte
from etl.secao import processar_secao
from etl.tse_csv import blocos_utf8
from polars.testing import assert_frame_equal

FIX = Path(__file__).parent / "fixtures"
ZIP_SECAO = FIX / "votacao_secao_2022_AC.zip"
BUJARI, CAPIXABA = 1200138, 1200179
LOCAIS_FIXTURE = 23


def origem() -> list[dict[str, str]]:
    with zipfile.ZipFile(ZIP_SECAO) as z, z.open("votacao_secao_2022_AC.csv") as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";"))


def montar_raw(base: Path) -> tuple[Path, Path]:
    """raw/ com as fixtures nos caminhos do catálogo; processed/ com os pré-requisitos."""
    raw, proc = base / "raw", base / "processed"
    for z in FIX.glob("*.zip"):
        if z.name.startswith("votacao_secao"):
            destino = raw / "tse" / "votacao_secao" / z.name
        else:
            fonte = z.name.removesuffix(".zip").removesuffix("_2022")
            destino = raw / "tse" / fonte / z.name
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(z.read_bytes())
    for pre in ("municipio_tse_ibge", "eleitorado_local_votacao", "votacao_candidato_munzona"):
        processar_fonte(pre, 2022, raw, proc)
    return raw, proc


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    raw, proc = montar_raw(tmp_path_factory.mktemp("secao"))
    processar_secao(2022, raw, proc, ufs=["AC"])
    return raw, proc


def ler(proc: Path, nome: str) -> pl.DataFrame:
    return pl.read_parquet(sorted((proc / nome).rglob("*.parquet")))


def test_contratos_e_chaves(ambiente: tuple[Path, Path]) -> None:
    for nome in ("votos_local", "totais_local", "locais_h3"):
        validar(ler(ambiente[1], nome), CONTRATOS[nome])


def test_total_de_controle_votos_nominais(ambiente: tuple[Path, Path]) -> None:
    """Σ votos_local = Σ QT_VOTOS das linhas com candidato (SQ_CANDIDATO > 0), por cargo."""
    esperado: dict[int, int] = {}
    for r in origem():
        if int(r["SQ_CANDIDATO"]) > 0:
            esperado[int(r["CD_CARGO"])] = esperado.get(int(r["CD_CARGO"]), 0) + int(r["QT_VOTOS"])
    df = ler(ambiente[1], "votos_local")
    obtido = dict(df.group_by("cd_cargo").agg(pl.col("votos").sum()).iter_rows())
    assert obtido == esperado
    assert (df["votos"] > 0).all()  # zero voto não vira linha
    assert set(df["cd_mun_ibge"].unique()) == {BUJARI, CAPIXABA}


def test_totais_por_local_somam_tudo(ambiente: tuple[Path, Path]) -> None:
    """nominais + legenda + brancos + nulos = todos os votos do cargo (comparecimento)."""
    esperado: dict[int, int] = {}
    for r in origem():
        esperado[int(r["CD_CARGO"])] = esperado.get(int(r["CD_CARGO"]), 0) + int(r["QT_VOTOS"])
    t = ler(ambiente[1], "totais_local")
    soma = t.group_by("cd_cargo").agg(
        (pl.col("votos_nominais") + pl.col("votos_legenda")
         + pl.col("votos_brancos") + pl.col("votos_nulos")).sum().alias("t")
    )  # fmt: skip
    assert dict(soma.iter_rows()) == esperado
    assert t["votos_brancos"].sum() == sum(
        int(r["QT_VOTOS"]) for r in origem() if r["NR_VOTAVEL"] == "95"
    )
    assert t["votos_nulos"].sum() == sum(
        int(r["QT_VOTOS"]) for r in origem() if r["NR_VOTAVEL"] == "96"
    )


def test_bate_com_munzona_por_candidato(ambiente: tuple[Path, Path]) -> None:
    """Para todo candidato do munzona, Σ locais = qt_votos_nominais do munzona."""
    mz = (
        pl.read_parquet(ambiente[1] / "votacao_candidato_munzona" / "ano=2022" / "AC.parquet")
        .filter(pl.col("nr_turno") == 1)
        .group_by("sq_candidato", "cd_cargo")
        .agg(pl.col("qt_votos_nominais").sum().alias("mz"))
    )
    vl = (
        ler(ambiente[1], "votos_local")
        .group_by("sq_candidato", "cd_cargo")
        .agg(pl.col("votos").sum())
    )
    j = mz.join(vl, on=["sq_candidato", "cd_cargo"], how="left").fill_null(0)
    assert j.height > 0
    assert j.filter(pl.col("mz") != pl.col("votos")).height == 0


def test_blocos_pequenos_dao_o_mesmo_resultado(ambiente: tuple[Path, Path], tmp_path: Path) -> None:
    """Um local cortado entre blocos é somado de novo no fim (partição por bytes)."""
    raw, proc = montar_raw(tmp_path)
    stats = processar_secao(2022, raw, proc, ufs=["AC"], bloco_bytes=20_000)
    assert stats["blocos"] > 3
    for nome in ("votos_local", "totais_local"):
        assert_frame_equal(
            ler(proc, nome).drop("dt_geracao"), ler(ambiente[1], nome).drop("dt_geracao")
        )


def test_blocos_utf8_reconstroem_o_arquivo(tmp_path: Path) -> None:
    linhas = 0
    soma = 0
    for bloco in blocos_utf8(ZIP_SECAO, "votacao_secao_2022_AC.csv", tmp_path, bloco_bytes=50_000):
        df = pl.read_csv(bloco.caminho, separator=";", infer_schema=False)
        assert df.height == bloco.linhas  # linhas contadas no fluxo = linhas lidas
        linhas += df.height
        soma += int(df["QT_VOTOS"].cast(pl.Int64).sum())
    assert linhas == len(origem())
    assert soma == sum(int(r["QT_VOTOS"]) for r in origem())
    assert not list(tmp_path.glob("*.csv"))  # cada bloco é apagado depois de usado


def test_locais_h3(ambiente: tuple[Path, Path]) -> None:
    lh = ler(ambiente[1], "locais_h3")
    assert lh.height == LOCAIS_FIXTURE
    for r in lh.iter_rows(named=True):
        c8 = h3.latlng_to_cell(r["lat"], r["lon"], 8)
        assert r["h3"] == c8
        assert r["h3_r7"] == h3.cell_to_parent(c8, 7)
        assert r["h3_r6"] == h3.cell_to_parent(c8, 6)
    el = ler(ambiente[1], "eleitorado_local_votacao").filter(pl.col("nr_turno") == 1)
    assert lh["aptos"].sum() == el["qt_eleitor_secao"].sum()


def test_todo_local_com_voto_tem_local_cadastrado(ambiente: tuple[Path, Path]) -> None:
    chaves = ["cd_municipio_tse", "nr_zona", "nr_local"]
    votos = ler(ambiente[1], "votos_local").select(chaves).unique()
    assert votos.join(
        ler(ambiente[1], "locais_h3").select(chaves), on=chaves, how="anti"
    ).is_empty()


def test_local_sem_coordenada_fica_fora_do_h3(tmp_path: Path) -> None:
    raw, proc = montar_raw(tmp_path)
    arq = next((proc / "eleitorado_local_votacao" / "ano=2022").glob("*.parquet"))
    el = pl.read_parquet(arq)
    alvo = el.filter(pl.col("nr_turno") == 1).row(0, named=True)
    sem = el.with_columns(
        pl.when(
            (pl.col("nr_turno") == 1)
            & (pl.col("cd_municipio_tse") == alvo["cd_municipio_tse"])
            & (pl.col("nr_zona") == alvo["nr_zona"])
            & (pl.col("nr_local_votacao") == alvo["nr_local_votacao"])
        )
        .then(None)
        .otherwise(pl.col(c))
        .alias(c)
        for c in ("nr_latitude", "nr_longitude")
    )
    sem.write_parquet(arq)
    stats = processar_secao(2022, raw, proc, ufs=["AC"])
    lh = ler(proc, "locais_h3")
    assert lh.height == LOCAIS_FIXTURE - 1
    assert stats["locais_sem_coordenada"] == 1
    esperado = sum(
        int(r["QT_VOTOS"])
        for r in origem()
        if int(r["SQ_CANDIDATO"]) > 0
        and (r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_LOCAL_VOTACAO"])
        == (str(alvo["cd_municipio_tse"]), str(alvo["nr_zona"]), str(alvo["nr_local_votacao"]))
    )
    assert stats["votos_sem_coordenada"] == esperado > 0
    # o voto continua em votos_local: só o H3 perde o local
    assert ler(proc, "votos_local")["votos"].sum() == sum(
        int(r["QT_VOTOS"]) for r in origem() if int(r["SQ_CANDIDATO"]) > 0
    )


def test_stats_de_controle(ambiente: tuple[Path, Path], tmp_path: Path) -> None:
    raw, proc = montar_raw(tmp_path)
    stats = processar_secao(2022, raw, proc, ufs=["AC"])
    assert stats["linhas_origem"] == len(origem())
    assert stats["votos_nominais"] == sum(
        int(r["QT_VOTOS"]) for r in origem() if int(r["SQ_CANDIDATO"]) > 0
    )
    assert stats["locais"] == LOCAIS_FIXTURE
    assert stats["locais_sem_coordenada"] == 0


def test_voto_a_mais_que_o_munzona_falha(tmp_path: Path) -> None:
    """Candidato do munzona com total diferente da soma dos locais derruba o processamento."""
    raw, proc = montar_raw(tmp_path)
    arq = next((proc / "votacao_candidato_munzona" / "ano=2022").glob("AC.parquet"))
    mz = pl.read_parquet(arq)
    idx = mz.with_row_index().filter(pl.col("qt_votos_nominais") > 0)["index"][0]
    mz.with_columns(
        pl.when(pl.int_range(pl.len()) == idx)
        .then(pl.col("qt_votos_nominais") + 1)
        .otherwise(pl.col("qt_votos_nominais"))
        .alias("qt_votos_nominais")
    ).write_parquet(arq)
    with pytest.raises(ErroProcessamento, match="munzona"):
        processar_secao(2022, raw, proc, ufs=["AC"])
    assert not list((proc / "votos_local").rglob("*.parquet"))  # nada publicado


def test_voto_nao_numerico_falha_alto(tmp_path: Path) -> None:
    raw, proc = montar_raw(tmp_path)
    zip_ = raw / "tse" / "votacao_secao" / "votacao_secao_2022_AC.zip"
    with zipfile.ZipFile(zip_) as z:
        texto = z.read("votacao_secao_2022_AC.csv").decode("latin-1")
    ruim = texto.replace(';"1";', ';"x";', 1) if ';"1";' in texto else texto
    linhas = texto.splitlines()
    cab = linhas[0].split(";")
    k = cab.index('"QT_VOTOS"')
    partes = linhas[1].split(";")
    partes[k] = "abc"
    linhas[1] = ";".join(partes)
    with zipfile.ZipFile(zip_, "w") as z:
        z.writestr("votacao_secao_2022_AC.csv", "\r\n".join(linhas).encode("latin-1"))
    assert ruim
    with pytest.raises(pl.exceptions.PolarsError):
        processar_secao(2022, raw, proc, ufs=["AC"])


def test_descartar_zip_apaga_so_depois_de_validar(tmp_path: Path) -> None:
    raw, proc = montar_raw(tmp_path)
    zip_ = raw / "tse" / "votacao_secao" / "votacao_secao_2022_AC.zip"
    processar_secao(2022, raw, proc, ufs=["AC"], descartar_zip=True)
    assert not zip_.exists()
    assert list((proc / "votos_local").rglob("AC.parquet"))


def test_zip_sem_linhas_de_dados_e_ignorado(tmp_path: Path) -> None:
    """`votacao_secao_2026_ZZ.zip` traz só o cabeçalho enquanto não há voto no exterior."""
    raw, proc = montar_raw(tmp_path)
    with zipfile.ZipFile(ZIP_SECAO) as z:
        cab = z.read("votacao_secao_2022_AC.csv").split(b"\r\n", 1)[0]
    vazio = raw / "tse" / "votacao_secao" / "votacao_secao_2022_ZZ.zip"
    with zipfile.ZipFile(vazio, "w") as z:
        z.writestr("votacao_secao_2022_ZZ.csv", cab + b"\r\n")
    stats = processar_secao(2022, raw, proc, ufs=["ZZ"])
    assert stats["linhas_origem"] == 0
    assert not list((proc / "votos_local").rglob("ZZ.parquet"))


def test_baixa_uf_a_uf_antes_de_processar(tmp_path: Path) -> None:
    """O gancho `baixar` recebe cada alvo; o ZIP pode nascer nele e sumir depois."""
    raw, proc = montar_raw(tmp_path)
    zip_ = raw / "tse" / "votacao_secao" / "votacao_secao_2022_AC.zip"
    conteudo = zip_.read_bytes()
    zip_.unlink()
    chamados: list[str] = []

    def baixar(alvo: object) -> None:
        chamados.append(alvo.destino)  # type: ignore[attr-defined]
        zip_.write_bytes(conteudo)

    processar_secao(2022, raw, proc, ufs=["AC"], baixar=baixar, descartar_zip=True)
    assert chamados == ["tse/votacao_secao/votacao_secao_2022_AC.zip"]
    assert not zip_.exists()
    assert list((proc / "votos_local").rglob("AC.parquet"))
