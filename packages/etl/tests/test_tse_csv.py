import zipfile
from datetime import date
from pathlib import Path

import polars as pl
import pytest
from contratos import Contrato
from etl.tse_csv import ler_membro, membros_dados, transcodificar

CT = Contrato(
    nome="t",
    colunas={"nome": pl.Utf8, "cod": pl.Int64, "qtd": pl.Int64, "valor": pl.Float64, "dt": pl.Date},
    chave=("nome",),
)
CSV = (
    '"NOME";"COD";"QTD";"VALOR";"DT"\r\n'
    '"São Paulo; capital";"#NE";"-1";"1,5";"07/10/2026"\r\n'
    '"Açaí";"-3";"12";"-9.82";"#NULO"\r\n'
).encode("latin-1")


@pytest.fixture
def zip_(tmp_path: Path) -> Path:
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("x_AC.csv", CSV)
        z.writestr("x_BR.csv", CSV)
        z.writestr("x_BRASIL.csv", CSV)
        z.writestr("leiame.pdf", b"%PDF")
    return p


def test_membros_ignora_brasil_e_nao_csv(zip_: Path) -> None:
    assert membros_dados(zip_) == ["x_AC.csv", "x_BR.csv"]


def test_transcodifica_latin1_para_utf8(zip_: Path, tmp_path: Path) -> None:
    out = transcodificar(zip_, "x_AC.csv", tmp_path / "u.csv")
    assert "São Paulo; capital" in out.read_text(encoding="utf-8")


def test_nulos_decimal_data_e_acentos(zip_: Path, tmp_path: Path) -> None:
    df = ler_membro(zip_, "x_AC.csv", CT, tmp_path).collect()
    assert df["nome"].to_list() == ["São Paulo; capital", "Açaí"]
    assert df["cod"].to_list() == [None, None]  # #NE e -3
    assert df["qtd"].to_list() == [None, 12]  # -1 → nulo
    assert df["valor"].to_list() == [1.5, -9.82]  # vírgula e ponto; negativo legítimo preservado
    assert df["dt"].to_list() == [date(2026, 10, 7), None]


def test_valor_nao_numerico_falha_alto(tmp_path: Path) -> None:
    p = tmp_path / "y.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(
            "y_AC.csv", '"NOME";"COD";"QTD";"VALOR";"DT"\r\n"a";"1";"abc";"1";"01/01/2022"\r\n'
        )
    with pytest.raises(pl.exceptions.PolarsError):
        ler_membro(p, "y_AC.csv", CT, tmp_path).collect()


def test_coluna_ausente_na_origem_falha_alto(tmp_path: Path) -> None:
    p = tmp_path / "z.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("z_AC.csv", '"NOME";"COD"\r\n"a";"1"\r\n')
    with pytest.raises(pl.exceptions.PolarsError):
        ler_membro(p, "z_AC.csv", CT, tmp_path).collect()
