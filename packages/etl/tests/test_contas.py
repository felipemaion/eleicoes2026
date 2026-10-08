"""Prestação de contas (fixture real do AC/2022, doadores anonimizados) e série IPCA."""

import csv
import io
import json
import shutil
import zipfile
from pathlib import Path

import polars as pl
import pytest
from contratos import CONTRATOS, validar
from etl.cli import main
from etl.ipca import ler_serie, processar_ipca
from etl.processar import CONTAS, ErroProcessamento, _normalizar_rotulos, processar_fonte
from etl.tse_csv import membros_dados

FIX = Path(__file__).parent / "fixtures"
ZIP = "prestacao_de_contas_eleitorais_candidatos_2022.zip"
VALOR = {
    "receitas_candidatos": ("VR_RECEITA", "vr_receita"),
    "despesas_contratadas_candidatos": ("VR_DESPESA_CONTRATADA", "vr_despesa_contratada"),
    "despesas_pagas_candidatos": ("VR_PAGTO_DESPESA", "vr_pagto_despesa"),
}


def _raw(base: Path, zip_origem: Path = FIX / ZIP) -> Path:
    destino = base / "raw" / "tse" / "prestacao_contas" / ZIP
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(zip_origem, destino)
    return base / "raw"


def oraculo(dataset: str, zip_: Path = FIX / ZIP) -> list[dict[str, str]]:
    """Linhas do dataset em todos os membros, menos `_BRASIL` (união duplicada)."""
    linhas: list[dict[str, str]] = []
    with zipfile.ZipFile(zip_) as z:
        for m in z.namelist():
            if m.startswith(dataset + "_20") and not m.endswith("_BRASIL.csv"):
                texto = io.TextIOWrapper(z.open(m), encoding="latin-1")
                linhas += list(csv.DictReader(texto, delimiter=";"))
    return linhas


def centavos(texto: str) -> int:
    return round(float(texto.replace(",", ".")) * 100)


@pytest.fixture(scope="module")
def pastas(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    base = tmp_path_factory.mktemp("contas")
    raw = _raw(base)
    proc = base / "processed"
    for nome in CONTAS:
        processar_fonte(nome, 2022, raw, proc)
    return raw, proc


def _ler(proc: Path, nome: str) -> pl.DataFrame:
    return pl.read_parquet(sorted((proc / nome).rglob("*.parquet")))


@pytest.mark.parametrize("nome", CONTAS)
def test_total_de_controle_contrato_e_brasil_ignorado(pastas: tuple[Path, Path], nome: str) -> None:
    df = _ler(pastas[1], nome)
    validar(df, CONTRATOS[nome])
    ref = oraculo(nome)
    assert len(ref) > 0
    csv_col, col = VALOR[nome]
    assert round(df[col].sum() * 100) == sum(centavos(r[csv_col]) for r in ref)
    assert df["qt_lancamentos"].sum() == len(ref)  # nada em dobro nem perdido
    assert df.height < len(ref)  # de fato agregou
    assert df["dt_geracao"].null_count() == 0


def test_sem_dados_de_pessoas_no_parquet(pastas: tuple[Path, Path]) -> None:
    for nome in CONTAS:
        cols = " ".join(_ler(pastas[1], nome).columns)
        for proibido in ("cpf", "doador", "fornecedor", "nm_", "titulo"):
            assert proibido not in cols


def test_despesa_paga_ligada_por_sq_prestador_contas(pastas: tuple[Path, Path]) -> None:
    pagas = _ler(pastas[1], "despesas_pagas_candidatos")
    assert pagas["sq_candidato"].null_count() == 0
    elo = {
        (r["SQ_PRESTADOR_CONTAS"], r["SQ_CANDIDATO"])
        for ds in ("receitas_candidatos", "despesas_contratadas_candidatos")
        for r in oraculo(ds)
    }
    obtido = set(pagas.select("sq_prestador_contas", "sq_candidato").unique().iter_rows())
    assert {(str(p), str(c)) for p, c in obtido} <= elo
    assert pagas.height > 0


def test_despesa_paga_sem_candidatura_falha_alto(tmp_path: Path) -> None:
    """Pagamento de prestador que não aparece em receitas/contratadas → erro, não nulo."""
    with zipfile.ZipFile(FIX / ZIP) as z:
        itens = {n: z.read(n) for n in z.namelist()}
    membro = "despesas_pagas_candidatos_2022_AC.csv"
    linhas = list(
        csv.reader(io.TextIOWrapper(io.BytesIO(itens[membro]), encoding="latin-1"), delimiter=";")
    )
    k = linhas[0].index("SQ_PRESTADOR_CONTAS")
    linhas[1][k] = "999999999"
    saida = io.StringIO()
    csv.writer(saida, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(linhas)
    itens[membro] = saida.getvalue().encode("latin-1")
    ruim = tmp_path / "ruim.zip"
    with zipfile.ZipFile(ruim, "w") as z:
        for n, b in itens.items():
            z.writestr(n, b)
    raw = _raw(tmp_path, ruim)
    with pytest.raises(ErroProcessamento, match="999999999"):
        processar_fonte("despesas_pagas_candidatos", 2022, raw, tmp_path / "proc")
    assert not list((tmp_path / "proc" / "despesas_pagas_candidatos").glob("ano=*"))


def test_membros_do_dataset_ignora_doador_originario(tmp_path: Path) -> None:
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as z:
        for n in (
            "receitas_candidatos_2022_AC.csv",
            "receitas_candidatos_2022_BR.csv",
            "receitas_candidatos_2022_BRASIL.csv",
            "receitas_candidatos_doador_originario_2022_AC.csv",
            "despesas_pagas_candidatos_2022_AC.csv",
            "leiame_receitas-candidatos.pdf",
        ):
            z.writestr(n, "x")
    assert membros_dados(p, "receitas_candidatos") == [
        "receitas_candidatos_2022_AC.csv",
        "receitas_candidatos_2022_BR.csv",
    ]


def test_rotulos_normalizados_so_nos_espacos() -> None:
    lf = pl.LazyFrame({"ds_x": ["  Recursos  de   pessoas físicas "], "outro": ["  a  "]})
    saida = _normalizar_rotulos(lf).collect()
    assert saida["ds_x"].to_list() == ["Recursos de pessoas físicas"]  # caixa e acento intactos
    assert saida["outro"].to_list() == ["  a  "]


def test_cli_dataset_contas(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = _raw(tmp_path)
    cod = main(["processar", "--ano", "2022", "--dataset", "contas", "--raiz-raw", str(raw),
                "--raiz-processed", str(tmp_path / "p")])  # fmt: skip
    assert cod == 0
    saida = capsys.readouterr().out
    assert all(nome in saida for nome in CONTAS)


# --- IPCA -------------------------------------------------------------------------------


def _json_ipca(raiz: Path, registros: list[dict[str, str]]) -> Path:
    destino = raiz / "bcb" / "ipca_433.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(registros), encoding="utf-8")
    return raiz


SERIE = [
    {"data": "01/10/2022", "valor": "0.59"},
    {"data": "01/11/2022", "valor": "0.41"},
    {"data": "01/12/2022", "valor": "0.62"},
    {"data": "01/01/2023", "valor": "-0.32"},
]


def test_ipca_indice_e_fator_batem_com_o_vetor_da_spec(tmp_path: Path) -> None:
    """Vetor `deflacao_ipca/tres_meses`: set→dez/2022 = 1,01628634."""
    raw = _json_ipca(tmp_path / "raw", SERIE)
    df = ler_serie(raw / "bcb" / "ipca_433.json")
    assert df["mes"].to_list() == ["2022-10", "2022-11", "2022-12", "2023-01"]
    ix = dict(df.select("mes", "indice").iter_rows())
    assert ix["2022-12"] / ix["2022-10"] == pytest.approx(1.0041 * 1.0062, abs=1e-9)
    assert df["indice"][0] == pytest.approx(100.59)


def test_ipca_parquet_validado(tmp_path: Path) -> None:
    raw = _json_ipca(tmp_path / "raw", SERIE)
    destino = processar_ipca(raw, tmp_path / "proc")
    df = pl.read_parquet(destino)
    validar(df, CONTRATOS["ipca"])
    assert df.height == 4
    assert not list((tmp_path / "proc" / "ipca").glob("*.tmp"))


def test_ipca_mes_faltante_falha_alto(tmp_path: Path) -> None:
    raw = _json_ipca(tmp_path / "raw", [SERIE[0], SERIE[2]])
    with pytest.raises(ErroProcessamento, match="2022-11"):
        processar_ipca(raw, tmp_path / "proc")


def test_ipca_valor_ilegivel_e_arquivo_ausente(tmp_path: Path) -> None:
    raw = _json_ipca(tmp_path / "raw", [{"data": "01/10/2022", "valor": "abc"}])
    with pytest.raises(ErroProcessamento, match="ilegível"):
        processar_ipca(raw, tmp_path / "proc")
    with pytest.raises(ErroProcessamento, match="não existe"):
        processar_ipca(tmp_path / "vazio", tmp_path / "proc")


def test_cli_dataset_ipca_sem_ano(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = _json_ipca(tmp_path / "raw", SERIE)
    cod = main(["processar", "--dataset", "ipca", "--raiz-raw", str(raw),
                "--raiz-processed", str(tmp_path / "p")])  # fmt: skip
    assert cod == 0
    assert "ipca.parquet" in capsys.readouterr().out
    assert main(["processar", "--raiz-raw", str(raw), "--raiz-processed", str(tmp_path / "p")]) == 2
