"""Redes sociais do TSE → ``redes_candidatos`` (só os grupos pedidos, só perfis válidos)."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import polars as pl
import pytest
from contratos import CONTRATOS, validar
from etl.fontes.catalogo import alvos
from etl.redes.tse import ErroRedes, processar_redes_tse, sqs_do_grupo

CABECALHO = (
    '"DT_GERACAO";"HH_GERACAO";"AA_ELEICAO";"SG_UF";"CD_TIPO_ELEICAO";"NM_TIPO_ELEICAO";'
    '"CD_ELEICAO";"DS_ELEICAO";"SQ_CANDIDATO";"NR_ORDEM_REDE_SOCIAL";"DS_URL"'
)


def _linha(uf: str, sq: int, ordem: int, url: str) -> str:
    return (
        f'"08/10/2026";"16:30:52";2026;"{uf}";2;"ELEIÇÃO ORDINÁRIA";6259;'
        f'"ELEIÇÕES GERAIS ESTADUAIS 2026";{sq};{ordem};"{url}"'
    )


@pytest.fixture
def ambiente(tmp_path: Path) -> dict[str, Path]:
    raw, proc, repo = tmp_path / "raw", tmp_path / "proc", tmp_path / "repo"
    # Candidatos: 1 e 2 são do 14; 3 está na lista (Beraldo/PP); 4 é de outro partido
    cand = pl.DataFrame(
        {"sq_candidato": [1, 2, 3, 4, 5], "nr_partido": [14, 14, 11, 99, 14]},
        schema={"sq_candidato": pl.Int64, "nr_partido": pl.Int16},
    )
    destino = proc / "consulta_cand/ano=2026"
    destino.mkdir(parents=True)
    cand.write_parquet(destino / "consulta_cand_2026.parquet")
    (repo / "config").mkdir(parents=True)
    (repo / "data/reference").mkdir(parents=True)
    (repo / "data/reference/lista.csv").write_text("sq_candidato_2026\n3\n", encoding="utf-8")
    (repo / "config/grupos.yaml").write_text(
        "grupos:\n"
        "  missao_2026: {rotulo: M, ano: 2026, criterio: {partido: 14}}\n"
        "  mbl_2026:\n"
        "    rotulo: B\n    ano: 2026\n"
        "    criterio:\n      partido: 14\n"
        "      lista: {arquivo: data/reference/lista.csv, coluna: sq_candidato_2026}\n",
        encoding="utf-8",
    )
    sp = [
        _linha("SP", 1, 1, "HTTPS://WWW.INSTAGRAM.COM/Fulano_Um?IGSH=abc"),
        _linha("SP", 1, 2, "https://www.facebook.com/fulano"),
        _linha("SP", 2, 1, "https://www.facebook.com/dois"),
        _linha("SP", 2, 2, "@dois.oficial"),  # arroba solto vale como Instagram
        _linha("SP", 3, 1, "https://www.instagram.com/p/ABC123/"),  # post, não perfil
        _linha("SP", 3, 2, "INSTAGRAM: BERALDO"),
        _linha("SP", 4, 1, "https://www.instagram.com/outro_partido"),  # fora dos grupos
    ]
    rj = [
        _linha("RJ", 5, 1, "https://instagram.com/cinco"),
        _linha("RJ", 5, 2, "https://instagram.com/cinco_reserva"),  # 2º perfil distinto
    ]
    pacote = raw / "tse/rede_social_candidato/rede_social_candidato_2026.zip"
    pacote.parent.mkdir(parents=True)
    with zipfile.ZipFile(pacote, "w") as z:
        z.writestr(
            "rede_social_candidato_2026_SP.csv", "\n".join([CABECALHO, *sp]).encode("latin-1")
        )
        z.writestr(
            "rede_social_candidato_2026_RJ.csv", "\n".join([CABECALHO, *rj]).encode("latin-1")
        )
        # união dos anteriores: lida junto duplicaria tudo
        z.writestr(
            "rede_social_candidato_2026_BRASIL.csv",
            "\n".join([CABECALHO, *sp, *rj]).encode("latin-1"),
        )
        z.writestr("leiame.pdf", b"%PDF")
    return {"raw": raw, "proc": proc, "repo": repo}


def test_catalogo_expoe_o_zip_de_redes_do_tse() -> None:
    [alvo] = alvos(2026, ["rede_social_candidato"])
    assert alvo.url == (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
        "rede_social_candidato_2026.zip"
    )
    assert alvo.destino == "tse/rede_social_candidato/rede_social_candidato_2026.zip"


def test_sqs_do_grupo_une_partido_e_lista(ambiente: dict[str, Path]) -> None:
    sqs = sqs_do_grupo(ambiente["proc"], ambiente["repo"], 2026, "mbl_2026")
    assert sqs == {1, 2, 3, 5}


def test_extrai_username_so_dos_grupos(ambiente: dict[str, Path]) -> None:
    stats = processar_redes_tse(
        2026, ambiente["raw"], ambiente["proc"], repo=ambiente["repo"], grupos=("mbl_2026",)
    )
    saida = ambiente["proc"] / "redes_candidatos/ano=2026/redes_candidatos.parquet"
    df = pl.read_parquet(saida).sort("sq_candidato")
    validar(df, CONTRATOS["redes_candidatos"])
    assert df.select("sq_candidato", "rede", "username", "nr_ordem", "principal").rows() == [
        (1, "instagram", "fulano_um", 1, True),
        (2, "instagram", "dois.oficial", 2, True),
        (3, "instagram", "beraldo", 2, True),
        (5, "instagram", "cinco", 1, True),
        (5, "instagram", "cinco_reserva", 2, False),  # 2º perfil: guardado, não principal
    ]
    assert df["dt_geracao"].unique().to_list() == [date(2026, 10, 8)]
    assert df.filter(pl.col("sq_candidato") == 1)["url_tse"][0].startswith("HTTPS://WWW.INSTAGRAM")
    assert stats["candidatos_no_grupo"] == 4
    assert stats["com_instagram"] == 4
    assert stats["perfis"] == 5
    assert stats["com_mais_de_um_perfil"] == 1  # candidato 5
    assert stats["urls_instagram_rejeitadas"] == 1  # o link de post do candidato 3


def test_candidato_do_grupo_sem_instagram_e_contado_nao_inventado(
    ambiente: dict[str, Path],
) -> None:
    bruto = ambiente["raw"] / "tse/rede_social_candidato/rede_social_candidato_2026.zip"
    with zipfile.ZipFile(bruto, "w") as z:
        z.writestr(
            "rede_social_candidato_2026_SP.csv",
            "\n".join([CABECALHO, _linha("SP", 1, 1, "https://www.facebook.com/x")]).encode(
                "latin-1"
            ),
        )
    stats = processar_redes_tse(
        2026, ambiente["raw"], ambiente["proc"], repo=ambiente["repo"], grupos=("mbl_2026",)
    )
    assert stats["com_instagram"] == 0
    assert stats["sem_instagram"] == 4
    df = pl.read_parquet(ambiente["proc"] / "redes_candidatos/ano=2026/redes_candidatos.parquet")
    assert df.height == 0


def test_sem_zip_falha_alto(ambiente: dict[str, Path]) -> None:
    (ambiente["raw"] / "tse/rede_social_candidato/rede_social_candidato_2026.zip").unlink()
    with pytest.raises(ErroRedes, match="rede_social_candidato"):
        processar_redes_tse(
            2026, ambiente["raw"], ambiente["proc"], repo=ambiente["repo"], grupos=("mbl_2026",)
        )
