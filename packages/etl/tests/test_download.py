import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from etl.cli import main
from etl.download import Baixador, DownloadError, Resultado
from etl.fontes.catalogo import Alvo
from etl.manifesto import Manifesto
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

CORPO = b"conteudo-zip" * 1000


@pytest.fixture
def cliente() -> Iterator[httpx.Client]:
    with httpx.Client() as c:
        yield c


def _baixador(
    tmp_path: Path, cliente: httpx.Client, esperas: list[float] | None = None
) -> Baixador:
    return Baixador(
        tmp_path,
        Manifesto(tmp_path / "manifesto.json"),
        cliente,
        dormir=(esperas if esperas is not None else []).append,
    )


def _alvo(srv: HTTPServer, caminho: str = "/a.zip") -> Alvo:
    return Alvo("teste", srv.url_for(caminho), "tse/teste/a.zip")


def test_baixa_e_registra_manifesto(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    httpserver.expect_request("/a.zip").respond_with_data(
        CORPO, headers={"ETag": '"v1"', "Last-Modified": "Mon, 05 Oct 2026 10:00:00 GMT"}
    )
    b = _baixador(tmp_path, cliente)
    assert b.baixar(_alvo(httpserver)) is Resultado.BAIXADO
    assert (tmp_path / "tse/teste/a.zip").read_bytes() == CORPO
    dados = json.loads((tmp_path / "manifesto.json").read_text())
    [e] = dados.values()
    assert e["sha256"] == hashlib.sha256(CORPO).hexdigest()
    assert e["bytes"] == len(CORPO)
    assert e["etag"] == '"v1"'
    assert e["baixado_em"].endswith("Z")
    assert not list(tmp_path.rglob("*.part"))


def test_pula_inalterado_por_etag(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    gets: list[int] = []

    def handler(req: Request) -> Response:
        if req.method == "GET":
            gets.append(1)
        return Response(CORPO, headers={"ETag": '"v1"'})

    httpserver.expect_request("/a.zip").respond_with_handler(handler)
    b = _baixador(tmp_path, cliente)
    b.baixar(_alvo(httpserver))
    assert b.baixar(_alvo(httpserver)) is Resultado.INALTERADO
    assert len(gets) == 1


def test_rebaixa_quando_etag_muda(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    b = _baixador(tmp_path, cliente)
    httpserver.expect_request("/a.zip").respond_with_data(b"v1", headers={"ETag": '"1"'})
    b.baixar(_alvo(httpserver))
    httpserver.clear()
    httpserver.expect_request("/a.zip").respond_with_data(b"v2-novo", headers={"ETag": '"2"'})
    assert b.baixar(_alvo(httpserver)) is Resultado.BAIXADO
    assert (tmp_path / "tse/teste/a.zip").read_bytes() == b"v2-novo"


def test_sem_validadores_decide_por_sha256(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    httpserver.expect_request("/a.zip").respond_with_data(CORPO, headers={"ETag": ""})
    b = _baixador(tmp_path, cliente)
    b.baixar(_alvo(httpserver))
    n = len(httpserver.log)
    assert b.baixar(_alvo(httpserver)) is Resultado.INALTERADO
    assert [r.method for r, _ in httpserver.log[n:]] == ["GET"]  # sem HEAD: o hash decidiu


def test_forcar_ignora_cache(httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client) -> None:
    httpserver.expect_request("/a.zip").respond_with_data(CORPO, headers={"ETag": '"v1"'})
    b = _baixador(tmp_path, cliente)
    b.baixar(_alvo(httpserver))
    # mesmo sha256 → conteúdo inalterado, mas houve GET (verificado pelo log do servidor)
    n = len(httpserver.log)
    b.baixar(_alvo(httpserver), forcar=True)
    assert any(r.method == "GET" for r, _ in httpserver.log[n:])


def test_arquivo_apagado_e_rebaixado(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    httpserver.expect_request("/a.zip").respond_with_data(CORPO, headers={"ETag": '"v1"'})
    b = _baixador(tmp_path, cliente)
    b.baixar(_alvo(httpserver))
    (tmp_path / "tse/teste/a.zip").unlink()
    assert b.baixar(_alvo(httpserver)) is Resultado.BAIXADO
    assert (tmp_path / "tse/teste/a.zip").exists()


def test_http_404_falha_alto_sem_retry(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    httpserver.expect_request("/a.zip").respond_with_data("nada", status=404)
    esperas: list[float] = []
    with pytest.raises(DownloadError, match="HTTP 404"):
        _baixador(tmp_path, cliente, esperas).baixar(_alvo(httpserver))
    assert esperas == []
    assert not (tmp_path / "tse/teste/a.zip").exists()
    assert not list(tmp_path.rglob("*.part"))


def test_http_503_retry_limitado_com_backoff(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    httpserver.expect_request("/a.zip").respond_with_data("x", status=503)
    esperas: list[float] = []
    with pytest.raises(DownloadError, match="4 tentativas"):
        _baixador(tmp_path, cliente, esperas).baixar(_alvo(httpserver))
    assert esperas == [1.0, 2.0, 4.0]


def test_recupera_apos_falha_transitoria(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    estado = {"n": 0}

    def handler(_: Request) -> Response:
        estado["n"] += 1
        return Response("x", status=503) if estado["n"] == 1 else Response(CORPO)

    httpserver.expect_request("/a.zip").respond_with_handler(handler)
    assert _baixador(tmp_path, cliente).baixar(_alvo(httpserver)) is Resultado.BAIXADO
    assert (tmp_path / "tse/teste/a.zip").read_bytes() == CORPO


class _CorpoQuebrado(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"parte"
        raise httpx.ReadError("conexão caiu")


@pytest.mark.parametrize("modo", ["queda", "content_length"])
def test_download_interrompido_nao_corrompe(tmp_path: Path, modo: str) -> None:
    destino = tmp_path / "tse/teste/a.zip"
    destino.parent.mkdir(parents=True)
    destino.write_bytes(b"original-integro")

    def responder(_: httpx.Request) -> httpx.Response:
        if modo == "queda":
            return httpx.Response(200, stream=_CorpoQuebrado())
        return httpx.Response(200, content=b"curto", headers={"Content-Length": "9999"})

    with httpx.Client(transport=httpx.MockTransport(responder)) as c:
        b = _baixador(tmp_path, c)
        with pytest.raises(DownloadError, match="4 tentativas"):
            b.baixar(Alvo("teste", "http://x/a.zip", "tse/teste/a.zip"))
    assert destino.read_bytes() == b"original-integro"
    assert not list(tmp_path.rglob("*.part"))


def test_retoma_descartando_parcial_antigo(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    destino = tmp_path / "tse/teste/a.zip"
    destino.parent.mkdir(parents=True)
    (destino.parent / "a.zip.part").write_bytes(b"lixo")
    httpserver.expect_request("/a.zip").respond_with_data(CORPO)
    _baixador(tmp_path, cliente).baixar(_alvo(httpserver))
    assert destino.read_bytes() == CORPO


def test_manifesto_ordenado_e_deterministico(tmp_path: Path) -> None:
    from etl.manifesto import Entrada

    m = Manifesto(tmp_path / "m.json")
    for u in ("https://b/2", "https://a/1"):
        m.registrar(Entrada(u, "c", "h", 1, "2026-10-07T00:00:00Z"))
    texto = (tmp_path / "m.json").read_text()
    assert list(json.loads(texto)) == ["https://a/1", "https://b/2"]
    m.salvar()
    assert (tmp_path / "m.json").read_text() == texto
    assert Manifesto(tmp_path / "m.json").obter("https://a/1") is not None
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_baixa_e_reporta_falha(
    httpserver: HTTPServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import etl.cli as cli

    httpserver.expect_request("/a.zip").respond_with_data(CORPO)
    monkeypatch.setattr(
        cli, "alvos", lambda *a, **k: [_alvo(httpserver), _alvo(httpserver, "/falta.zip")]
    )
    httpserver.expect_request("/falta.zip").respond_with_data("", status=404)
    codigo = main(["baixar", "--ano", "2026", "--raiz", str(tmp_path)])
    saida = capsys.readouterr()
    assert codigo == 1
    assert "baixado" in saida.out
    assert "HTTP 404" in saida.err


def test_cli_ano_invalido(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["baixar", "--ano", "1999"]) == 2
    assert "erro" in capsys.readouterr().err


def _com_transporte(tmp_path: Path, responder, esperas=None):  # type: ignore[no-untyped-def]
    c = httpx.Client(transport=httpx.MockTransport(responder))
    return _baixador(tmp_path, c, esperas), Alvo("t", "http://x/a.json", "ibge/a.json")


def _ok(corpo: bytes = CORPO, **headers: str) -> httpx.Response:
    """Resposta simulada sem Content-Length (o MockTransport não conta bytes no fio)."""
    return httpx.Response(200, stream=httpx.ByteStream(corpo), headers=headers)


def test_resposta_gzip_nao_parece_truncada(
    httpserver: HTTPServer, tmp_path: Path, cliente: httpx.Client
) -> None:
    import gzip

    bruto = gzip.compress(CORPO)
    httpserver.expect_request("/a.zip").respond_with_data(
        bruto, headers={"Content-Encoding": "gzip"}
    )
    assert _baixador(tmp_path, cliente).baixar(_alvo(httpserver)) is Resultado.BAIXADO
    assert (tmp_path / "tse/teste/a.zip").read_bytes() == CORPO


@pytest.mark.parametrize("status", [403, 405])
def test_head_4xx_cai_no_get(tmp_path: Path, status: int) -> None:
    def responder(req: httpx.Request) -> httpx.Response:
        if req.method == "HEAD":
            return httpx.Response(status)
        return _ok(ETag='"v1"')

    b, alvo = _com_transporte(tmp_path, responder)
    b.baixar(alvo)
    assert b.baixar(alvo) is Resultado.INALTERADO  # GET refeito, sha256 igual
    assert (tmp_path / alvo.destino).read_bytes() == CORPO


def test_429_repetido_respeitando_retry_after(tmp_path: Path) -> None:
    n = {"i": 0}

    def responder(_: httpx.Request) -> httpx.Response:
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return _ok()

    esperas: list[float] = []
    b, alvo = _com_transporte(tmp_path, responder, esperas)
    assert b.baixar(alvo) is Resultado.BAIXADO
    assert esperas == [7.0]


def test_too_many_redirects_vira_download_error(tmp_path: Path) -> None:
    def responder(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://x/a.json"})

    b, alvo = _com_transporte(tmp_path, responder)
    with pytest.raises(DownloadError):
        b.baixar(alvo)


def test_disco_cheio_vira_download_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    def falha(*_: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", falha)
    b, alvo = _com_transporte(tmp_path, lambda _: _ok())
    with pytest.raises(DownloadError, match="No space"):
        b.baixar(alvo)
    assert not list(tmp_path.rglob("*.part"))


def test_fsync_chamado_antes_do_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    chamadas: list[int] = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (chamadas.append(fd), real(fd))[1])
    b, alvo = _com_transporte(tmp_path, lambda _: _ok())
    b.baixar(alvo)
    assert chamadas


def test_verificar_detecta_corrupcao(tmp_path: Path) -> None:
    b, alvo = _com_transporte(tmp_path, lambda _: _ok())
    assert b.verificar(alvo) == "ausente"
    b.baixar(alvo)
    assert b.verificar(alvo) == "ok"
    (tmp_path / alvo.destino).write_bytes(b"corrompido")
    assert b.verificar(alvo) == "corrompido"


def test_cli_laco_segue_apos_erro_e_verifica(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import etl.cli as cli

    httpserver.expect_request("/a.zip").respond_with_data(CORPO)
    monkeypatch.setattr(cli, "alvos", lambda *a, **k: [_alvo(httpserver)])
    assert main(["baixar", "--ano", "2026", "--raiz", str(tmp_path)]) == 0
    assert main(["baixar", "--ano", "2026", "--raiz", str(tmp_path), "--verificar"]) == 0
    (tmp_path / "tse/teste/a.zip").write_bytes(b"x")
    assert main(["baixar", "--ano", "2026", "--raiz", str(tmp_path), "--verificar"]) == 1
