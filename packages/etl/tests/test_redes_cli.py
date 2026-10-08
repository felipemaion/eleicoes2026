"""CLI das redes: leitura do .env sem vazar valores, códigos de saída e aviso de vencimento."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from contratos import CONTRATOS
from etl import cli
from etl.redes.execucao import carregar_env
from etl.redes.meta import ErroLimite, ErroMeta


def test_carregar_env_le_pares_ignora_comentarios_e_nao_sobrescreve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        '# comentário\nMETA_TOKEN="abc=="\nMETA_APP_ID=123\n\nvazio\nJA_EXISTE=do_arquivo\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("META_TOKEN", raising=False)
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.setenv("JA_EXISTE", "do_ambiente")
    env = carregar_env(arquivo)
    assert env["META_TOKEN"] == "abc=="  # noqa: S105 - valor sintético
    assert env["META_APP_ID"] == "123"
    assert env["JA_EXISTE"] == "do_ambiente"  # o ambiente vence o arquivo


def test_sem_token_falha_com_mensagem_clara_e_sem_valores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("META_TOKEN", raising=False)
    codigo = cli.main(["redes-coletar", "--env", str(tmp_path / "nao_existe.env")])
    assert codigo == 1
    assert "META_TOKEN" in capsys.readouterr().err


def _preparar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    destino = tmp_path / "proc/redes_candidatos/ano=2026"
    destino.mkdir(parents=True)
    pl.DataFrame(
        {
            "ano_eleicao": [2026], "sq_candidato": [1], "rede": ["instagram"],
            "username": ["ana"], "url_tse": ["https://instagram.com/ana"], "nr_ordem": [1],
            "principal": [True], "dt_geracao": [date(2026, 10, 8)],
        },
        schema=dict(CONTRATOS["redes_candidatos"].colunas),
    ).write_parquet(destino / "redes_candidatos.parquet")  # fmt: skip
    env = tmp_path / ".env"
    env.write_text("META_TOKEN=tok\nMETA_APP_ID=1\nMETA_APP_SECRET=s\n", encoding="utf-8")
    for k in ("META_TOKEN", "META_APP_ID", "META_APP_SECRET"):
        monkeypatch.delenv(k, raising=False)

    class Falso:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.chamadas = 0

        def conta_instagram(self) -> str:
            return "IG"

        def validade_token(self, *_: str) -> datetime:
            return datetime(2026, 10, 20, tzinfo=UTC)

    monkeypatch.setattr(cli, "ClienteMeta", Falso)
    return [
        "redes-coletar", "--env", str(env), "--raiz-raw", str(tmp_path / "raw"),
        "--raiz-processed", str(tmp_path / "proc"), "--hoje", "2026-10-08",
    ]  # fmt: skip


def test_aviso_de_token_perto_de_vencer_vai_para_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _preparar(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "coletar", lambda *_, **__: {"perfis": {}, "chamadas": 0})
    assert cli.main(argv) == 0
    assert "vence em 12 dias" in capsys.readouterr().err


def test_limite_persistente_sai_com_3_para_o_agendador_retomar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _preparar(tmp_path, monkeypatch)

    def estoura(*_: Any, **__: Any) -> None:
        raise ErroLimite("limite")

    monkeypatch.setattr(cli, "coletar", estoura)
    assert cli.main(argv) == 3
    assert "retome" in capsys.readouterr().err


def test_erro_de_token_sai_com_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _preparar(tmp_path, monkeypatch)

    def estoura(*_: Any, **__: Any) -> None:
        raise ErroMeta("Graph API código 190")

    monkeypatch.setattr(cli, "coletar", estoura)
    assert cli.main(argv) == 1
    assert "190" in capsys.readouterr().err
