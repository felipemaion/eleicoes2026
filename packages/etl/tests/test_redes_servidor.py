"""Execução no servidor: promoção atômica da série, status.json e aviso de expiração do token."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from contratos import CONTRATOS
from etl.redes.meta import ErroLimite, ErroMeta
from etl.redes.servidor import ConfigServidor, executar

AGORA = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
ENV = {"META_TOKEN": "tok", "META_APP_ID": "1", "META_APP_SECRET": "s"}


class ClienteFalso:
    def __init__(self, vence: datetime | None = datetime(2026, 12, 7, tzinfo=UTC)) -> None:
        self.vence = vence
        self.chamadas = 0

    def conta_instagram(self) -> str:
        return "IG"

    def validade_token(self, *_: str) -> datetime | None:
        if isinstance(self.vence, Exception):
            raise self.vence
        return self.vence


def _candidatos(datasets: Path) -> None:
    destino = datasets / "redes_candidatos/ano=2026"
    destino.mkdir(parents=True)
    pl.DataFrame(
        {
            "ano_eleicao": [2026], "sq_candidato": [1], "rede": ["instagram"],
            "username": ["ana"], "url_tse": ["https://instagram.com/ana"], "nr_ordem": [1],
            "principal": [True], "dt_geracao": [datetime(2026, 10, 8).date()],
        },
        schema=dict(CONTRATOS["redes_candidatos"].colunas),
    ).write_parquet(destino / "redes_candidatos.parquet")  # fmt: skip


def _perfil(dia: int) -> dict[str, Any]:
    return {
        "sq_candidato": 1, "ano_eleicao": 2026, "rede": "instagram", "username": "ana",
        "status": "ok", "followers_count": 100 + dia, "follows_count": 1, "media_count": 2,
        "coletado_em": datetime(2026, 10, dia, 6, tzinfo=UTC),
    }  # fmt: skip


def _serie(saida: Path, dias: list[int]) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        [_perfil(d) for d in dias], schema=dict(CONTRATOS["redes_perfis"].colunas)
    ).write_parquet(saida / "redes_perfis.parquet")


@pytest.fixture
def cfg(tmp_path: Path) -> ConfigServidor:
    _candidatos(tmp_path / "datasets")
    return ConfigServidor(
        datasets=tmp_path / "datasets", saida=tmp_path / "saida", ano=2026,
        tentativas=3, espera_s=0, aviso_dias=14,
    )  # fmt: skip


def _coleta_que_acrescenta(dia: int, perfis: int = 1):  # type: ignore[no-untyped-def]
    def fn(
        _c: Any, _id: str, _cands: Any, *, raiz_raw: Path, raiz_processed: Path, **__: Any
    ) -> Any:
        arq = raiz_processed / "redes/redes_perfis.parquet"
        antes = (
            pl.read_parquet(arq)
            if arq.exists()
            else pl.DataFrame(schema=dict(CONTRATOS["redes_perfis"].colunas))
        )
        novo = pl.DataFrame([_perfil(dia)], schema=dict(CONTRATOS["redes_perfis"].colunas))
        arq.parent.mkdir(parents=True, exist_ok=True)
        pl.concat([antes, novo]).write_parquet(arq)
        return {"perfis": {"ok": perfis}, "usernames": perfis, "chamadas": 3}

    return fn


def _status(cfg: ConfigServidor) -> dict[str, Any]:
    st: dict[str, Any] = json.loads((cfg.saida / "status.json").read_text(encoding="utf-8"))
    return st


def test_sucesso_acrescenta_snapshot_sem_perder_os_anteriores(cfg: ConfigServidor) -> None:
    _serie(cfg.saida, [10, 11])
    cod = executar(
        cfg, ENV, cliente=ClienteFalso(), coletar_fn=_coleta_que_acrescenta(15), agora=lambda: AGORA
    )
    assert cod == 0
    dias = pl.read_parquet(cfg.saida / "redes_perfis.parquet")["coletado_em"].dt.day().to_list()
    assert sorted(dias) == [10, 11, 15]
    assert not (cfg.saida / ".novo").exists()
    st = _status(cfg)
    assert st["resultado"] == "ok"
    assert st["perfis_coletados"] == 1
    assert st["coletado_em"].endswith("Z") or "+00:00" in st["coletado_em"]


def test_primeira_coleta_cria_a_serie(cfg: ConfigServidor) -> None:
    assert (
        executar(
            cfg,
            ENV,
            cliente=ClienteFalso(),
            coletar_fn=_coleta_que_acrescenta(15),
            agora=lambda: AGORA,
        )
        == 0
    )
    assert (cfg.saida / "redes_perfis.parquet").exists()


def test_falha_no_meio_preserva_a_serie_anterior(cfg: ConfigServidor) -> None:
    _serie(cfg.saida, [10, 11])
    antes = (cfg.saida / "redes_perfis.parquet").read_bytes()

    def quebra(*_: Any, raiz_processed: Path, **__: Any) -> None:
        (raiz_processed / "redes").mkdir(parents=True, exist_ok=True)
        (raiz_processed / "redes/redes_perfis.parquet").write_bytes(b"lixo parcial")
        raise ErroMeta("Graph API código 200: app bloqueado")

    cod = executar(cfg, ENV, cliente=ClienteFalso(), coletar_fn=quebra, agora=lambda: AGORA)
    assert cod == 1
    assert (cfg.saida / "redes_perfis.parquet").read_bytes() == antes
    st = _status(cfg)
    assert st["resultado"] == "erro"
    assert "200" in st["motivo"]
    assert not (cfg.saida / ".novo").exists()


def test_excecao_nao_prevista_grava_status_erro_preserva_serie_e_relanca(
    cfg: ConfigServidor,
) -> None:
    _serie(cfg.saida, [10, 11])
    antes = (cfg.saida / "redes_perfis.parquet").read_bytes()

    def quebra(*_: Any, raiz_processed: Path, **__: Any) -> None:
        (raiz_processed / "redes").mkdir(parents=True, exist_ok=True)
        (raiz_processed / "redes/redes_perfis.parquet").write_bytes(b"lixo parcial")
        raise KeyError("followers_count")

    with pytest.raises(KeyError):
        executar(cfg, ENV, cliente=ClienteFalso(), coletar_fn=quebra, agora=lambda: AGORA)
    assert (cfg.saida / "redes_perfis.parquet").read_bytes() == antes
    st = _status(cfg)
    assert st["resultado"] == "erro"
    assert st["motivo"].startswith("KeyError")
    assert "followers_count" in st["motivo"]
    assert not (cfg.saida / ".novo").exists()


def test_limite_retoma_e_depois_conclui(cfg: ConfigServidor) -> None:
    chamadas = {"n": 0}
    boa = _coleta_que_acrescenta(15)

    def instavel(*a: Any, **k: Any) -> dict[str, Any]:
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise ErroLimite("limite")
        resultado: dict[str, Any] = boa(*a, **k)
        return resultado

    esperas: list[float] = []
    cod = executar(
        cfg,
        ENV,
        cliente=ClienteFalso(),
        coletar_fn=instavel,
        agora=lambda: AGORA,
        dormir=esperas.append,
    )
    assert cod == 0
    assert chamadas["n"] == 3
    assert len(esperas) == 2
    assert _status(cfg)["resultado"] == "ok"


def test_limite_persistente_sai_3_e_registra_limite(cfg: ConfigServidor) -> None:
    def sempre(*_: Any, **__: Any) -> None:
        raise ErroLimite("limite")

    cod = executar(
        cfg,
        ENV,
        cliente=ClienteFalso(),
        coletar_fn=sempre,
        agora=lambda: AGORA,
        dormir=lambda _s: None,
    )
    assert cod == 3
    assert _status(cfg)["resultado"] == "limite"


def test_token_vencido_falha_antes_de_gastar_chamadas(cfg: ConfigServidor) -> None:
    usado = {"n": 0}

    def nao(*_: Any, **__: Any) -> None:
        usado["n"] += 1

    cliente = ClienteFalso(vence=datetime(2026, 10, 1, tzinfo=UTC))
    assert executar(cfg, ENV, cliente=cliente, coletar_fn=nao, agora=lambda: AGORA) == 1
    assert usado["n"] == 0
    st = _status(cfg)
    assert st["resultado"] == "erro"
    assert "venceu" in st["motivo"]


def test_token_perto_de_vencer_coleta_e_sai_com_aviso_4(
    cfg: ConfigServidor, capsys: pytest.CaptureFixture[str]
) -> None:
    cliente = ClienteFalso(vence=datetime(2026, 10, 25, tzinfo=UTC))  # 10 dias
    cod = executar(
        cfg, ENV, cliente=cliente, coletar_fn=_coleta_que_acrescenta(15), agora=lambda: AGORA
    )
    assert cod == 4
    assert (cfg.saida / "redes_perfis.parquet").exists()  # a série foi promovida mesmo assim
    st = _status(cfg)
    assert st["resultado"] == "ok"
    assert "vence em 10 dias" in st["motivo"]
    assert "vence em 10 dias" in capsys.readouterr().err


def test_token_a_15_dias_nao_avisa_com_limite_de_14(cfg: ConfigServidor) -> None:
    cliente = ClienteFalso(vence=datetime(2026, 10, 30, tzinfo=UTC))  # 15 dias
    assert (
        executar(
            cfg, ENV, cliente=cliente, coletar_fn=_coleta_que_acrescenta(15), agora=lambda: AGORA
        )
        == 0
    )


def test_sem_credenciais_falha_com_mensagem(cfg: ConfigServidor) -> None:
    cod = executar(cfg, {}, cliente=None, coletar_fn=lambda *_, **__: {}, agora=lambda: AGORA)
    assert cod == 1
    assert "META_TOKEN" in _status(cfg)["motivo"]


def test_sem_entrada_redes_candidatos_falha(tmp_path: Path) -> None:
    cfg = ConfigServidor(
        datasets=tmp_path / "d",
        saida=tmp_path / "s",
        ano=2026,
        tentativas=1,
        espera_s=0,
        aviso_dias=14,
    )
    cod = executar(
        cfg, ENV, cliente=ClienteFalso(), coletar_fn=lambda *_, **__: {}, agora=lambda: AGORA
    )
    assert cod == 1
    assert "redes_candidatos" in _status(cfg)["motivo"]


def test_cli_simular_confere_ambiente_sem_rede(
    cfg: ConfigServidor, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from etl import cli

    monkeypatch.setenv("ELEICOES_DIR_DATASETS", str(cfg.datasets))
    monkeypatch.setenv("ELEICOES_DIR_SAIDA", str(cfg.saida))
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    assert cli.main(["redes-servidor", "--simular"]) == 0
    assert "ok" in capsys.readouterr().out
    monkeypatch.delenv("META_TOKEN")
    assert cli.main(["redes-servidor", "--simular"]) == 1
