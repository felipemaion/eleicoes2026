"""Parsers sobre fixtures reais (2 municípios do AC, 2022). O oráculo é o módulo ``csv``."""

import csv
import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from contratos import CONTRATOS, validar
from etl.manifesto import Entrada, Manifesto
from etl.processar import ErroProcessamento, hash_pessoa, processar_fonte

FIX = Path(__file__).parent / "fixtures"
SAL = "sal-de-teste"
BUJARI_IBGE = 1200138
CAPIXABA_IBGE = 1200179


def oraculo(fonte: str, nome_zip: str) -> list[dict[str, str]]:
    """Linhas de todos os CSVs do ZIP, menos o `_BRASIL` (união duplicada)."""
    linhas: list[dict[str, str]] = []
    with zipfile.ZipFile(FIX / nome_zip) as z:
        for m in z.namelist():
            if m.endswith(".csv") and not m.endswith("_BRASIL.csv"):
                with z.open(m) as f:
                    linhas += list(
                        csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"), delimiter=";")
                    )
    return linhas


@pytest.fixture(scope="module")
def raiz(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """raw/ com as fixtures nos caminhos do catálogo + processed/ já com o crosswalk."""
    base = tmp_path_factory.mktemp("etl")
    raw, proc = base / "raw", base / "processed"
    for z in FIX.glob("*.zip"):
        fonte = z.name.removesuffix(".zip").removesuffix("_2022")
        destino = raw / "tse" / fonte / z.name
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(z.read_bytes())
    processar_fonte("municipio_tse_ibge", 2022, raw, proc)
    return raw, proc


def _ler(proc: Path, fonte: str) -> pl.DataFrame:
    return pl.read_parquet(sorted((proc / fonte).rglob("*.parquet")))


def test_crosswalk(raiz: tuple[Path, Path]) -> None:
    df = _ler(raiz[1], "municipio_tse_ibge")
    validar(df, CONTRATOS["municipio_tse_ibge"])
    assert df.filter(pl.col("cd_municipio_tse") == 1007)["cd_mun_ibge"].to_list() == [BUJARI_IBGE]


@pytest.mark.parametrize(
    ("fonte", "zip_", "coluna_total"),
    [
        ("votacao_candidato_munzona", "votacao_candidato_munzona_2022.zip", "QT_VOTOS_NOMINAIS"),
        ("detalhe_votacao_munzona", "detalhe_votacao_munzona_2022.zip", "QT_APTOS"),
        (
            "votacao_partido_munzona",
            "votacao_partido_munzona_2022.zip",
            "QT_TOTAL_VOTOS_LEG_VALIDOS",
        ),
    ],
)
def test_total_de_controle_e_contrato(
    raiz: tuple[Path, Path], fonte: str, zip_: str, coluna_total: str
) -> None:
    processar_fonte(fonte, 2022, *raiz)
    df = _ler(raiz[1], fonte)
    validar(df, CONTRATOS[fonte])
    ref = oraculo(fonte, zip_)
    assert len(ref) > 0
    assert df.height == len(ref)  # `_BRASIL` ignorado: nada em dobro
    assert df[coluna_total.lower()].sum() == sum(int(r[coluna_total]) for r in ref)
    assert set(df["cd_mun_ibge"].unique().to_list()) <= {BUJARI_IBGE, CAPIXABA_IBGE}
    assert df["cd_mun_ibge"].null_count() == 0


def test_votacao_inclui_presidente_do_arquivo_br(raiz: tuple[Path, Path]) -> None:
    df = _ler(raiz[1], "votacao_candidato_munzona")
    assert {1, 3, 6, 7} <= set(df["cd_cargo"].to_list())  # 1 = presidente (arquivo _BR)


def test_nulos_do_tse_viram_nulo(raiz: tuple[Path, Path]) -> None:
    df = _ler(raiz[1], "votacao_candidato_munzona")
    assert df["nr_federacao"].min() != -1  # -1 = "sem federação" → nulo
    assert not df.filter(pl.col("nr_federacao") < 0).height


def test_consulta_cand_sem_pii_e_com_pessoa_id(raiz: tuple[Path, Path]) -> None:
    processar_fonte("consulta_cand", 2022, *raiz, sal=SAL)
    df = _ler(raiz[1], "consulta_cand")
    validar(df, CONTRATOS["consulta_cand"])
    assert not {c for c in df.columns if "cpf" in c or "titulo" in c or "email" in c}
    assert df["pessoa_id"].str.len_chars().unique().to_list() == [64]
    assert df["pessoa_id"].n_unique() == df.height  # CPFs sintéticos distintos


def test_pessoa_id_ver_adr_0004() -> None:
    import hashlib

    esperado = hashlib.sha256(b"sal" + b"12345678901").hexdigest()
    assert hash_pessoa("123.456.789-01", None, "sal") == esperado
    assert hash_pessoa(None, "0001 2345 6789", "sal") != esperado  # cai no título
    assert hash_pessoa("-4", "-4", "sal") is None  # não divulgável
    assert hash_pessoa("12345678901", None, "outro") != esperado


def test_consulta_cand_exige_sal(raiz: tuple[Path, Path]) -> None:
    with pytest.raises(ErroProcessamento, match="PESSOA_ID_SAL"):
        processar_fonte("consulta_cand", 2022, *raiz, sal=None)


def test_vagas(raiz: tuple[Path, Path]) -> None:
    processar_fonte("consulta_vagas", 2022, *raiz)
    df = _ler(raiz[1], "consulta_vagas")
    validar(df, CONTRATOS["consulta_vagas"])
    ref = oraculo("consulta_vagas", "consulta_vagas_2022.zip")
    assert df["qt_vaga"].sum() == sum(int(r["QT_VAGA"]) for r in ref)
    assert df.filter((pl.col("sg_uf") == "AC") & (pl.col("cd_cargo") == 6))[
        "qt_vaga"
    ].to_list() == [8]


def test_locais_agregados_por_local(raiz: tuple[Path, Path]) -> None:
    processar_fonte("eleitorado_local_votacao", 2022, *raiz)
    df = _ler(raiz[1], "eleitorado_local_votacao")
    validar(df, CONTRATOS["eleitorado_local_votacao"])
    ref = oraculo("eleitorado_local_votacao", "eleitorado_local_votacao_2022.zip")
    assert df["qt_eleitor_secao"].sum() == sum(int(r["QT_ELEITOR_SECAO"]) for r in ref)
    assert df["qt_secoes"].sum() == len(ref)
    assert df.height == len(
        {(r["NR_TURNO"], r["NR_ZONA"], r["NR_LOCAL_VOTACAO"], r["CD_MUNICIPIO"]) for r in ref}
    )
    assert df["nr_latitude"].dtype == pl.Float64


def test_municipio_sem_crosswalk_falha_alto(raiz: tuple[Path, Path], tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    (proc / "municipio_tse_ibge" / "ano=2022").mkdir(parents=True)
    xw = _ler(raiz[1], "municipio_tse_ibge").filter(pl.col("cd_municipio_tse") != 1007)
    xw.write_parquet(proc / "municipio_tse_ibge" / "ano=2022" / "municipio_tse_ibge.parquet")
    with pytest.raises(ErroProcessamento, match="1007"):
        processar_fonte("detalhe_votacao_munzona", 2022, raiz[0], proc)
    assert not list((proc / "detalhe_votacao_munzona").rglob("*.parquet"))  # nada publicado


def test_manifesto_recebe_dt_geracao(raiz: tuple[Path, Path], tmp_path: Path) -> None:
    caminho = "tse/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip"
    m = Manifesto(tmp_path / "m.json")
    m.registrar(Entrada("http://x", caminho, "h", 1, "2026-10-07T00:00:00Z"))
    processar_fonte("detalhe_votacao_munzona", 2022, *raiz, manifesto=m)
    assert json.loads((tmp_path / "m.json").read_text())["http://x"]["dt_geracao"] == "2026-10-07"


def test_cli_processar(raiz: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    from etl.cli import main

    cod = main(["processar", "--ano", "2022", "--fonte", "consulta_vagas",
                "--raiz-raw", str(raiz[0]), "--raiz-processed", str(raiz[1])])  # fmt: skip
    assert cod == 0
    assert "consulta_vagas" in capsys.readouterr().out
