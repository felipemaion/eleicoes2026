"""Parsers sobre fixtures reais (2 municípios do AC, 2022). O oráculo é o módulo ``csv``."""

import csv
import io
import json
import shutil
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

    esperado = hashlib.sha256(b"sal" + b"52998224725").hexdigest()
    assert hash_pessoa("529.982.247-25", None, "sal") == esperado
    assert hash_pessoa(None, "0001 2345 6789", "sal") != esperado  # cai no título
    assert hash_pessoa("-4", "-4", "sal") is None  # não divulgável
    assert hash_pessoa("52998224725", None, "outro") != esperado


@pytest.mark.parametrize(
    "cpf",
    ["00000000000", "11111111111", "123.456.789-01", "529982247251", "5299822472", "abc"],
)
def test_pessoa_id_rejeita_cpf_malformado(cpf: str) -> None:
    """Zeros, dígitos repetidos, DV errado e ≠ 11 dígitos não identificam ninguém."""
    assert hash_pessoa(cpf, None, "sal") is None


def test_pessoa_id_titulo_exige_12_digitos() -> None:
    assert hash_pessoa(None, "12345678", "sal") is None  # 8 dígitos
    assert hash_pessoa(None, "1234567890123", "sal") is None  # 13 dígitos
    assert hash_pessoa(None, "000000000000", "sal") is None  # repetidos
    assert hash_pessoa(None, "123456789012", "sal") is not None


def test_cpf_nunca_toca_processed(raiz: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Em nenhum momento observável há arquivo com CPF sob processed/; o temporário some."""
    import tempfile

    import etl.processar as proc_mod

    raw, proc = raiz
    ref = oraculo("consulta_cand", "consulta_cand_2022.zip")
    cpfs = {r["NR_CPF_CANDIDATO"].encode() for r in ref}
    temp = Path(tempfile.gettempdir())
    antes = {p.name for p in temp.glob("etl-*")}
    vistos = {"fora": False}
    original = proc_mod.hash_pessoa

    def espiao(cpf: str | None, titulo: str | None, sal: str) -> str | None:
        for arq in proc.rglob("*"):
            if arq.is_file() and any(c in arq.read_bytes() for c in cpfs):
                raise AssertionError(f"CPF em disco sob processed/: {arq}")
        vistos["fora"] = any(
            any(c in a.read_bytes() for c in cpfs)
            for d in temp.glob("etl-*")
            for a in d.glob("*.csv")
        )
        return original(cpf, titulo, sal)

    monkeypatch.setattr(proc_mod, "hash_pessoa", espiao)
    processar_fonte("consulta_cand", 2022, raw, proc, sal=SAL)
    assert vistos["fora"]  # o espião de fato viu o CSV (fora de processed/)
    assert {p.name for p in temp.glob("etl-*")} == antes  # nada sobra
    assert not list(proc.rglob("*.utf8.csv"))
    assert not list(proc.rglob(".etl-*"))


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


def _zip_de_locais(destino: Path, ordem: list[int]) -> Path:
    """Zip com um local de duas seções e coordenadas diferentes, linhas na ordem dada."""
    with zipfile.ZipFile(FIX / "eleitorado_local_votacao_2022.zip") as z:
        [membro] = z.namelist()
        texto = io.TextIOWrapper(z.open(membro), encoding="latin-1")
        linhas = list(csv.reader(texto, delimiter=";"))
    cab, base = linhas[0], linhas[1]
    i = {c: k for k, c in enumerate(cab)}
    secoes = []
    for sec, lat, lon in ((10, "-9,10", "-67,10"), (20, "-9,90", "-67,90"), (30, "-1,0", "-1,0")):
        r = list(base)
        r[i["NR_SECAO"]], r[i["NR_LATITUDE"]], r[i["NR_LONGITUDE"]] = str(sec), lat, lon
        secoes.append(r)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(cab)
    w.writerows(secoes[k] for k in ordem)
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("eleitorado_local_votacao_2022.csv", saida.getvalue().encode("latin-1"))
    return destino


def test_locais_deterministico_e_coordenada_de_uma_secao(
    raiz: tuple[Path, Path], tmp_path: Path
) -> None:
    resultados = []
    for k, ordem in enumerate(([0, 1, 2], [2, 1, 0], [1, 2, 0])):
        raw = tmp_path / f"raw{k}"
        destino = raw / "tse/eleitorado_local_votacao/eleitorado_local_votacao_2022.zip"
        destino.parent.mkdir(parents=True)
        _zip_de_locais(destino, ordem)
        proc = tmp_path / f"proc{k}"
        shutil.copytree(raiz[1] / "municipio_tse_ibge", proc / "municipio_tse_ibge")
        processar_fonte("eleitorado_local_votacao", 2022, raw, proc)
        df = _ler(proc, "eleitorado_local_votacao")
        assert df.height == 1
        resultados.append(df.row(0, named=True))
    assert resultados[0] == resultados[1] == resultados[2]
    # seção 10 (menor) vence; o par lat/lon é da MESMA seção, e o sentinela (-1;-1) é ignorado
    assert (resultados[0]["nr_latitude"], resultados[0]["nr_longitude"]) == (-9.10, -67.10)
    assert resultados[0]["qt_secoes"] == 3


def test_total_de_controle_vem_do_texto_com_sentinelas(
    raiz: tuple[Path, Path], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Esperado = soma do texto ≥ 0; `-1/-3` nunca entram (nem inflam nem escondem divergência)."""
    raw = tmp_path / "raw"
    destino = raw / "tse/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip"
    destino.parent.mkdir(parents=True)
    with zipfile.ZipFile(FIX / "detalhe_votacao_munzona_2022.zip") as z:
        linhas = list(
            csv.reader(
                io.TextIOWrapper(z.open("detalhe_votacao_munzona_2022_AC.csv"), encoding="latin-1"),
                delimiter=";",
            )
        )
    cab = linhas[0]
    k = cab.index("QT_COMPARECIMENTO")
    corpo = [list(r) for r in linhas[1:]]
    corpo[0][k], corpo[1][k] = "-1", "-3"
    esperado = sum(int(r[k]) for r in corpo if int(r[k]) >= 0)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerows([cab, *corpo])
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("detalhe_votacao_munzona_2022_AC.csv", saida.getvalue().encode("latin-1"))
    proc = tmp_path / "proc"
    shutil.copytree(raiz[1] / "municipio_tse_ibge", proc / "municipio_tse_ibge")
    with caplog.at_level("INFO", logger="etl.processar"):
        processar_fonte("detalhe_votacao_munzona", 2022, raw, proc)
    df = _ler(proc, "detalhe_votacao_munzona")
    assert df["qt_comparecimento"].sum() == esperado
    assert df.height == len(corpo)
    assert "qt_comparecimento → 2 sentinela" in caplog.text


def test_publicacao_atomica_nada_parcial(raiz: tuple[Path, Path], tmp_path: Path) -> None:
    """Um membro inválido derruba o ano inteiro: nem o ano antigo muda, nem sobra staging."""
    raw = tmp_path / "raw"
    destino = raw / "tse/consulta_vagas/consulta_vagas_2022.zip"
    destino.parent.mkdir(parents=True)
    shutil.copy(FIX / "consulta_vagas_2022.zip", destino)
    proc = tmp_path / "proc"
    processar_fonte("consulta_vagas", 2022, raw, proc)
    antes = {p.name: p.read_bytes() for p in (proc / "consulta_vagas/ano=2022").glob("*.parquet")}
    with zipfile.ZipFile(destino) as z:
        itens = {n: z.read(n) for n in z.namelist()}
    ruim = sorted(n for n in itens if n.endswith(".csv") and not n.endswith("_BRASIL.csv"))[-1]
    itens[ruim] = itens[ruim].replace(b'"QT_VAGA"', b'"QT_VAGAS"')  # coluna ausente
    with zipfile.ZipFile(destino, "w") as z:
        for n, b in itens.items():
            z.writestr(n, b)
    with pytest.raises(Exception, match="QT_VAGA"):
        processar_fonte("consulta_vagas", 2022, raw, proc)
    depois = {p.name: p.read_bytes() for p in (proc / "consulta_vagas/ano=2022").glob("*.parquet")}
    assert depois == antes
    assert not list((proc / "consulta_vagas").glob("ano=2022.*"))
