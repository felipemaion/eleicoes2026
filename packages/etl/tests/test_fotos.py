"""Fotos oficiais: extração do ZIP do TSE, filtro por candidatura, WebP 160×200 e manifesto."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from etl.fontes.catalogo import alvos
from etl.fotos import ErroFotos, processar_fotos, selecionar_sqs
from PIL import Image


def _jpeg(largura: int, altura: int, cor: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), cor).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def zip_ac(tmp_path: Path) -> Path:
    """ZIP no leiaute do TSE: ``F<UF><SQ>_div.jpg|jpeg`` + leiame.pdf."""
    caminho = tmp_path / "raw/tse/fotos/foto_cand2026_AC_div.zip"
    caminho.parent.mkdir(parents=True)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("FAC10000000001_div.jpg", _jpeg(161, 225, (200, 0, 0)))
        z.writestr("FAC10000000002_div.jpeg", _jpeg(111, 155, (0, 200, 0)))
        z.writestr("FAC10000000003_div.jpg", _jpeg(300, 200, (0, 0, 200)))  # fora da seleção
        z.writestr("leiame.pdf", b"%PDF")
    return caminho


def test_catalogo_expoe_fotos_por_uf_com_url_do_cdn() -> None:
    [alvo] = alvos(2026, ["fotos"], uf="AC")
    assert alvo.url == (
        "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/fotos/"
        "foto_cand2026_AC_div.zip"
    )
    assert alvo.destino == "tse/fotos/foto_cand2026_AC_div.zip"
    assert all(a.destino != "tse/fotos/foto_cand2022_ZZ_div.zip" for a in alvos(2022, ["fotos"]))


def test_extrai_filtra_redimensiona_e_grava_manifesto(zip_ac: Path, tmp_path: Path) -> None:
    saida = tmp_path / "fotos"
    stats = processar_fotos(2026, [zip_ac], saida, sqs={"10000000001", "10000000002", "999"})

    assert stats["extraidas"] == 2
    assert stats["fora_da_selecao"] == 1
    assert stats["sem_foto"] == 1  # "999" está na seleção mas não no ZIP
    for sq in ("10000000001", "10000000002"):
        with Image.open(saida / "2026" / f"{sq}.webp") as im:
            assert im.format == "WEBP"
            assert im.size == (160, 200)
    assert not (saida / "2026/10000000003.webp").exists()

    manifesto = json.loads((saida / "manifesto.json").read_text())
    entrada = manifesto["fotos"]["2026/10000000001"]
    assert entrada["arquivo"] == "2026/10000000001.webp"
    assert entrada["origem"] == "foto_cand2026_AC_div.zip:FAC10000000001_div.jpg"
    assert len(entrada["sha256"]) == 64


def test_idempotente_e_acumula_entre_ufs(zip_ac: Path, tmp_path: Path) -> None:
    saida = tmp_path / "fotos"
    processar_fotos(2026, [zip_ac], saida, sqs={"10000000001"})
    antes = (saida / "2026/10000000001.webp").read_bytes()
    processar_fotos(2026, [zip_ac], saida, sqs={"10000000001", "10000000002"})
    assert (saida / "2026/10000000001.webp").read_bytes() == antes
    chaves = set(json.loads((saida / "manifesto.json").read_text())["fotos"])
    assert chaves == {"2026/10000000001", "2026/10000000002"}


def test_zip_corrompido_falha_alto(tmp_path: Path) -> None:
    ruim = tmp_path / "foto_cand2026_AC_div.zip"
    ruim.write_bytes(b"nao e zip")
    with pytest.raises(ErroFotos, match=r"foto_cand2026_AC_div\.zip"):
        processar_fotos(2026, [ruim], tmp_path / "fotos", sqs={"1"})


def test_imagem_ilegivel_falha_alto(tmp_path: Path) -> None:
    z = tmp_path / "foto_cand2026_AC_div.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("FAC10000000001_div.jpg", b"lixo")
    with pytest.raises(ErroFotos, match=r"FAC10000000001_div\.jpg"):
        processar_fotos(2026, [z], tmp_path / "fotos", sqs={"10000000001"})


def test_selecionar_sqs_cargos_1_a_8_mais_partido_14(tmp_path: Path) -> None:
    pasta = tmp_path / "consulta_cand/ano=2026"
    pasta.mkdir(parents=True)
    pl.DataFrame(
        {
            "ano_eleicao": [2026] * 4,
            "sq_candidato": [1, 2, 3, 4],  # Int64 no Parquet; os ZIPs usam o sq como texto
            "cd_cargo": [1, 9, 9, 9],  # presidente e três suplentes
            "nr_partido": [10, 14, 15, 10],
        }
    ).write_parquet(pasta / "BR.parquet")
    assert selecionar_sqs(tmp_path, 2026) == {"1", "2"}  # presidente + suplente do 14
