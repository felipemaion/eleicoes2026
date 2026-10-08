"""Testes do ledger de registro de desenvolvimento.

O ledger e a fonte de verdade sobre tempo, tokens e custo do projeto. Se ele
mentir, todo o relatorio mente junto — por isso os casos abaixo fixam os
precos e os multiplicadores de cache com numeros conferiveis a mao.
"""

from __future__ import annotations

import json
from pathlib import Path

import ledger
import pytest

UM_MILHAO = 1_000_000


def usage(**kwargs: int) -> dict[str, object]:
    """Monta um bloco `usage` no formato que o transcript do Claude Code emite."""
    return {
        "input_tokens": kwargs.get("input_tokens", 0),
        "output_tokens": kwargs.get("output_tokens", 0),
        "cache_read_input_tokens": kwargs.get("cache_read", 0),
        "cache_creation": {
            "ephemeral_1h_input_tokens": kwargs.get("cache_1h", 0),
            "ephemeral_5m_input_tokens": kwargs.get("cache_5m", 0),
        },
    }


class TestCusto:
    def test_entrada_e_saida_usam_o_preco_de_tabela(self) -> None:
        # Opus 5: US$ 5,00 por 1M de entrada e US$ 25,00 por 1M de saida.
        custo = ledger.estimate_cost(
            ledger.TokenUsage.from_transcript(
                usage(input_tokens=UM_MILHAO, output_tokens=UM_MILHAO)
            ),
            "claude-opus-5",
        )
        assert custo == pytest.approx(30.0)

    def test_leitura_de_cache_custa_um_decimo_da_entrada(self) -> None:
        custo = ledger.estimate_cost(
            ledger.TokenUsage.from_transcript(usage(cache_read=UM_MILHAO)), "claude-opus-5"
        )
        assert custo == pytest.approx(0.5)

    def test_escrita_de_cache_de_uma_hora_custa_o_dobro_da_entrada(self) -> None:
        custo = ledger.estimate_cost(
            ledger.TokenUsage.from_transcript(usage(cache_1h=UM_MILHAO)), "claude-opus-5"
        )
        assert custo == pytest.approx(10.0)

    def test_escrita_de_cache_de_cinco_minutos_custa_um_quarto_a_mais(self) -> None:
        custo = ledger.estimate_cost(
            ledger.TokenUsage.from_transcript(usage(cache_5m=UM_MILHAO)), "claude-opus-5"
        )
        assert custo == pytest.approx(6.25)

    @pytest.mark.parametrize(
        ("modelo", "esperado"),
        [("claude-sonnet-5", 12.0), ("claude-haiku-4-5", 6.0)],
    )
    def test_cada_modelo_tem_seu_proprio_preco(self, modelo: str, esperado: float) -> None:
        custo = ledger.estimate_cost(
            ledger.TokenUsage.from_transcript(
                usage(input_tokens=UM_MILHAO, output_tokens=UM_MILHAO)
            ),
            modelo,
        )
        assert custo == pytest.approx(esperado)

    def test_sufixo_de_janela_de_contexto_nao_muda_o_modelo(self) -> None:
        # O runtime reporta "claude-opus-5[1m]"; a tabela de precos conhece a base.
        base = ledger.TokenUsage.from_transcript(usage(output_tokens=UM_MILHAO))
        assert ledger.estimate_cost(base, "claude-opus-5[1m]") == ledger.estimate_cost(
            base, "claude-opus-5"
        )

    def test_sufixo_de_data_nao_muda_o_modelo(self) -> None:
        # O runtime reporta ids datados como "claude-haiku-4-5-20251001"; sem
        # normalizar, o custo desse modelo sai como zero e some do relatorio.
        base = ledger.TokenUsage.from_transcript(usage(output_tokens=UM_MILHAO))
        assert ledger.estimate_cost(base, "claude-haiku-4-5-20251001") == pytest.approx(5.0)
        assert ledger.estimate_cost(base, "claude-sonnet-5-20260101") == pytest.approx(10.0)

    def test_modelo_desconhecido_falha_alto_em_vez_de_estimar_errado(self) -> None:
        with pytest.raises(ledger.UnknownModelError, match="claude-inexistente"):
            ledger.estimate_cost(ledger.TokenUsage(), "claude-inexistente")


class TestLeituraDeTranscript:
    def escreve(self, tmp_path: Path, *linhas: object) -> Path:
        arquivo = tmp_path / "sessao.jsonl"
        arquivo.write_text("\n".join(json.dumps(linha) for linha in linhas), encoding="utf-8")
        return arquivo

    def mensagem(
        self, ident: str, *, sidechain: bool = False, saida: int = 10
    ) -> dict[str, object]:
        return {
            "type": "assistant",
            "timestamp": "2026-08-25T17:45:02.429Z",
            "sessionId": "s1",
            "isSidechain": sidechain,
            "gitBranch": "chore/ledger-registro",
            "message": {
                "id": ident,
                "model": "claude-opus-5",
                "usage": usage(output_tokens=saida),
            },
        }

    def test_le_apenas_mensagens_do_assistente(self, tmp_path: Path) -> None:
        arquivo = self.escreve(
            tmp_path,
            {"type": "user", "message": {"role": "user"}},
            self.mensagem("msg_1"),
            {"type": "file-history-snapshot"},
        )
        registros = list(ledger.parse_transcript(arquivo))
        assert [r.message_id for r in registros] == ["msg_1"]

    def test_ignora_mensagem_repetida(self, tmp_path: Path) -> None:
        # Retomada de sessao e compactacao reescrevem mensagens ja gravadas.
        arquivo = self.escreve(tmp_path, self.mensagem("msg_1"), self.mensagem("msg_1"))
        assert len(list(ledger.parse_transcript(arquivo))) == 1

    def test_ignora_linha_corrompida_sem_derrubar_a_leitura(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "sessao.jsonl"
        arquivo.write_text(
            "{nao e json\n" + json.dumps(self.mensagem("msg_1")) + "\n", encoding="utf-8"
        )
        assert len(list(ledger.parse_transcript(arquivo))) == 1

    def test_distingue_subagente_do_laco_principal(self, tmp_path: Path) -> None:
        arquivo = self.escreve(
            tmp_path, self.mensagem("msg_1"), self.mensagem("msg_2", sidechain=True)
        )
        registros = list(ledger.parse_transcript(arquivo))
        assert [r.is_subagent for r in registros] == [False, True]

    def test_mensagem_sem_uso_registrado_e_descartada(self, tmp_path: Path) -> None:
        sem_uso = {"type": "assistant", "message": {"id": "msg_1", "model": "claude-opus-5"}}
        arquivo = self.escreve(tmp_path, sem_uso)
        assert list(ledger.parse_transcript(arquivo)) == []


class TestAgregacao:
    def test_soma_tokens_e_custo_por_modelo(self) -> None:
        registros = [
            ledger.TranscriptRecord(
                message_id=f"m{i}",
                model="claude-opus-5" if i < 2 else "claude-sonnet-5",
                timestamp="2026-08-25T17:45:02.429Z",
                session_id="s1",
                is_subagent=False,
                usage=ledger.TokenUsage(output_tokens=UM_MILHAO),
            )
            for i in range(3)
        ]
        resumo = ledger.summarize(registros)
        assert resumo["claude-opus-5"].messages == 2
        assert resumo["claude-opus-5"].usage.output_tokens == 2 * UM_MILHAO
        assert resumo["claude-opus-5"].cost_usd == pytest.approx(50.0)
        assert resumo["claude-sonnet-5"].cost_usd == pytest.approx(10.0)


class TestEventosDeTarefa:
    def test_evento_gravado_pode_ser_lido_de_volta(self, tmp_path: Path) -> None:
        destino = tmp_path / "2026-08.jsonl"
        evento = ledger.TaskEvent(
            task="T-001", papel="backend", modelo="claude-sonnet-5", acao="inicio"
        )
        ledger.append_event(destino, evento)
        lidos = ledger.read_events(destino)
        assert [e.task for e in lidos] == ["T-001"]
        assert lidos[0].timestamp, "o evento precisa carimbar o horario"

    def test_eventos_acumulam_em_vez_de_sobrescrever(self, tmp_path: Path) -> None:
        destino = tmp_path / "2026-08.jsonl"
        for acao in ("inicio", "fim"):
            ledger.append_event(
                destino,
                ledger.TaskEvent(task="T-001", papel="backend", modelo="x", acao=acao),
            )
        assert [e.acao for e in ledger.read_events(destino)] == ["inicio", "fim"]


class TestRelatorio:
    def test_relatorio_mostra_custo_por_modelo_e_total(self) -> None:
        resumo = {
            "claude-opus-5": ledger.ModelSummary(
                messages=2, usage=ledger.TokenUsage(output_tokens=UM_MILHAO), cost_usd=25.0
            ),
            "claude-haiku-4-5": ledger.ModelSummary(
                messages=1, usage=ledger.TokenUsage(output_tokens=UM_MILHAO), cost_usd=5.0
            ),
        }
        texto = ledger.render_report(resumo, events=[])
        assert "claude-opus-5" in texto
        assert "30.00" in texto, "o total precisa aparecer no relatorio"


class TestColetaEntreArquivos:
    def test_nao_conta_a_mesma_mensagem_em_dois_transcripts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Retomar uma sessao cria um transcript novo que repete o historico.
        raiz = tmp_path / "projeto"
        raiz.mkdir()
        destino = tmp_path / "home" / ".claude" / "projects"
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        pasta = destino / ledger.transcript_dir(raiz).name
        pasta.mkdir(parents=True)
        mensagem = {
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "model": "claude-opus-5",
                "usage": usage(output_tokens=100),
            },
        }
        for nome in ("a.jsonl", "b.jsonl"):
            (pasta / nome).write_text(json.dumps(mensagem) + "\n", encoding="utf-8")
        assert len(ledger.collect_records(raiz)) == 1

    def test_projeto_sem_transcript_devolve_lista_vazia(self, tmp_path: Path) -> None:
        assert ledger.collect_records(tmp_path / "inexistente") == []

    def test_slug_do_diretorio_espelha_o_caminho_do_projeto(self, tmp_path: Path) -> None:
        assert ledger.transcript_dir(tmp_path).name.startswith("-")


class TestRobustez:
    def test_modelo_sem_preco_nao_derruba_o_resumo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Um modelo novo nao pode impedir o relatorio de sair; vira aviso, nao excecao.
        registro = ledger.TranscriptRecord(
            message_id="m1",
            model="claude-do-futuro",
            timestamp="",
            session_id="s1",
            is_subagent=False,
            usage=ledger.TokenUsage(output_tokens=100),
        )
        resumo = ledger.summarize([registro])
        assert resumo["claude-do-futuro"].cost_usd == 0.0
        assert "sem preco de tabela" in capsys.readouterr().err

    def test_prompt_soma_o_resto_nao_cacheado_com_o_que_veio_do_cache(self) -> None:
        uso = ledger.TokenUsage.from_transcript(
            usage(input_tokens=2, cache_read=100, cache_1h=50, cache_5m=8)
        )
        assert uso.prompt_tokens == 160

    def test_evento_com_campo_desconhecido_e_lido_sem_quebrar(self, tmp_path: Path) -> None:
        destino = tmp_path / "2026-08.jsonl"
        destino.write_text(
            json.dumps({"task": "T-1", "papel": "qa", "modelo": "m", "acao": "fim", "novo": 1})
            + "\n",
            encoding="utf-8",
        )
        assert ledger.read_events(destino)[0].task == "T-1"

    def test_ledger_inexistente_significa_nenhum_evento(self, tmp_path: Path) -> None:
        assert ledger.read_events(tmp_path / "nao-existe.jsonl") == []

    def test_linha_corrompida_no_ledger_e_ignorada(self, tmp_path: Path) -> None:
        destino = tmp_path / "2026-08.jsonl"
        destino.write_text(
            "{quebrado\n"
            + json.dumps({"task": "T-1", "papel": "qa", "modelo": "m", "acao": "fim"})
            + "\n",
            encoding="utf-8",
        )
        assert len(ledger.read_events(destino)) == 1


class TestLinhaDeComando:
    def test_evento_pela_cli_chega_ao_ledger_do_mes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELEICOES_ROOT", str(tmp_path))
        codigo = ledger.main(
            [
                "evento",
                "--task",
                "T-001",
                "--papel",
                "backend",
                "--modelo",
                "claude-sonnet-5",
                "--acao",
                "inicio",
                "--fase",
                "0",
            ]
        )
        assert codigo == 0
        eventos = ledger.read_events(ledger.ledger_path(tmp_path))
        assert [(e.task, e.acao, e.fase) for e in eventos] == [("T-001", "inicio", "0")]

    def test_relatorio_pela_cli_escreve_o_arquivo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELEICOES_ROOT", str(tmp_path))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        assert ledger.main(["relatorio"]) == 0
        assert (tmp_path / "docs" / "registro" / "RELATORIO.md").is_file()

    def test_coletar_sem_transcript_sinaliza_falha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ELEICOES_ROOT", str(tmp_path))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        assert ledger.main(["coletar"]) == 1


class TestTranscriptsDosAgentes:
    """Cada agente roda com o diretorio de trabalho na propria worktree, o que
    faz o Claude Code criar um diretorio de transcript separado. Sem varrer
    esses diretorios, o registro so contabiliza o orquestrador — e o custo do
    projeto sai menor do que e."""

    def prepara(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        raiz = tmp_path / "projeto"
        raiz.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        return raiz

    def grava(self, pasta: Path, ident: str, modelo: str = "claude-opus-5") -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{ident}.jsonl").write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "id": ident,
                        "model": modelo,
                        "usage": usage(output_tokens=100),
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_conta_os_transcripts_das_worktrees_dos_agentes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = self.prepara(tmp_path, monkeypatch)
        base = ledger.transcript_dir(raiz)
        self.grava(base, "msg_orquestrador")
        self.grava(
            base.parent / f"{base.name}--worktrees-backend", "msg_backend", "claude-sonnet-5"
        )
        self.grava(base.parent / f"{base.name}--worktrees-ops", "msg_ops", "claude-haiku-4-5")

        modelos = sorted(ledger.normalize_model(r.model) for r in ledger.collect_records(raiz))
        assert modelos == ["claude-haiku-4-5", "claude-opus-5", "claude-sonnet-5"]

    def test_nao_confunde_com_outro_projeto_de_nome_parecido(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Um projeto vizinho cujo slug comeca igual nao pode entrar na conta.
        raiz = self.prepara(tmp_path, monkeypatch)
        base = ledger.transcript_dir(raiz)
        self.grava(base, "msg_nosso")
        self.grava(base.parent / f"{base.name}-outro-projeto", "msg_alheio")

        assert [r.message_id for r in ledger.collect_records(raiz)] == ["msg_nosso"]


class TestConsolidacao:
    """O ledger vivo fica fora do git porque os agentes escrevem nele o tempo
    todo. A consolidacao passa os eventos para o arquivo versionado quando o
    orquestrador decide — e precisa ser repetivel sem duplicar."""

    def evento(self, task: str, acao: str = "inicio") -> ledger.TaskEvent:
        return ledger.TaskEvent(task=task, papel="backend", modelo="claude-sonnet-5", acao=acao)

    def test_passa_os_eventos_do_vivo_para_o_versionado(self, tmp_path: Path) -> None:
        ledger.append_event(ledger.ledger_path(tmp_path), self.evento("T-001"))
        ledger.append_event(ledger.ledger_path(tmp_path), self.evento("T-001", "fim"))

        assert ledger.consolidate(tmp_path) == 2
        gravados = ledger.read_events(ledger.consolidated_ledger_path(tmp_path))
        assert [e.acao for e in gravados] == ["inicio", "fim"]

    def test_consolidar_duas_vezes_nao_duplica(self, tmp_path: Path) -> None:
        # O orquestrador consolida quando quer; rodar de novo nao pode inflar o
        # registro nem inventar trabalho que nao aconteceu.
        ledger.append_event(ledger.ledger_path(tmp_path), self.evento("T-001"))
        ledger.consolidate(tmp_path)

        assert ledger.consolidate(tmp_path) == 0
        assert len(ledger.read_events(ledger.consolidated_ledger_path(tmp_path))) == 1

    def test_eventos_novos_entram_sem_reescrever_os_antigos(self, tmp_path: Path) -> None:
        ledger.append_event(ledger.ledger_path(tmp_path), self.evento("T-001"))
        ledger.consolidate(tmp_path)
        ledger.append_event(ledger.ledger_path(tmp_path), self.evento("T-002"))

        assert ledger.consolidate(tmp_path) == 1
        assert [e.task for e in ledger.read_events(ledger.consolidated_ledger_path(tmp_path))] == [
            "T-001",
            "T-002",
        ]

    def test_o_arquivo_vivo_fica_fora_do_git(self, tmp_path: Path) -> None:
        # `.raw.jsonl` e o padrao ja ignorado no .gitignore desde o primeiro commit.
        assert ledger.ledger_path(tmp_path).name.endswith(".raw.jsonl")
        assert not ledger.consolidated_ledger_path(tmp_path).name.endswith(".raw.jsonl")


class TestMensagensSinteticas:
    """`<synthetic>` nao e modelo: e o proprio Claude Code falando com o usuario
    do lado do cliente — aviso de limite de sessao, por exemplo. Zero tokens,
    zero custo, nenhuma chamada de API.

    Contar isso como "modelo sem preco" polui o relatorio com uma linha fantasma
    e, pior, gasta o aviso de falha alta: se todo relatorio traz um aviso
    ignoravel, o dia em que aparecer um modelo real sem preco ninguem repara.
    """

    def sintetica(self, ident: str) -> dict[str, object]:
        return {
            "type": "assistant",
            "message": {
                "id": ident,
                "model": "<synthetic>",
                "usage": usage(),
                "content": [{"type": "text", "text": "You've hit your session limit"}],
            },
        }

    def test_mensagem_sintetica_nao_entra_no_resumo(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "sessao.jsonl"
        real = {
            "type": "assistant",
            "message": {
                "id": "msg_real",
                "model": "claude-opus-5",
                "usage": usage(output_tokens=100),
            },
        }
        arquivo.write_text(
            json.dumps(self.sintetica("msg_sint")) + "\n" + json.dumps(real) + "\n",
            encoding="utf-8",
        )
        registros = list(ledger.parse_transcript(arquivo))
        assert [r.message_id for r in registros] == ["msg_real"]

    def test_resumo_nao_ganha_linha_fantasma(self, capsys: pytest.CaptureFixture[str]) -> None:
        registros = [
            ledger.TranscriptRecord(
                message_id="m1",
                model="<synthetic>",
                timestamp="",
                session_id="s1",
                is_subagent=False,
                usage=ledger.TokenUsage(),
            )
        ]
        assert ledger.summarize(registros) == {}
        assert "sem preco de tabela" not in capsys.readouterr().err

    def test_modelo_real_desconhecido_continua_avisando_alto(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A excecao e so para `<synthetic>`. Modelo de verdade sem preco continua
        # gritando, que e o comportamento que protege o numero.
        registros = [
            ledger.TranscriptRecord(
                message_id="m1",
                model="claude-do-futuro",
                timestamp="",
                session_id="s1",
                is_subagent=False,
                usage=ledger.TokenUsage(output_tokens=100),
            )
        ]
        resumo = ledger.summarize(registros)
        assert "claude-do-futuro" in resumo
        assert "sem preco de tabela" in capsys.readouterr().err
