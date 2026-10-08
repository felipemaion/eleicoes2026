"""Testes do formatador de eventos do painel-monitor.

O monitor le um arquivo enquanto ele e escrito: encontrar linha pela metade e
o caso normal, nao a excecao. Estes testes fixam esse comportamento.
"""

from __future__ import annotations

import io
import json

import formatar_eventos
import pytest


class TestFormatacao:
    def test_linha_traz_hora_acao_papel_tarefa_e_descricao(self) -> None:
        linha = formatar_eventos.formatar(
            {
                "timestamp": "2026-08-25T18:22:31+00:00",
                "acao": "inicio",
                "papel": "backend",
                "task": "T-014",
                "descricao": "motor de ToolInstance",
            }
        )
        assert "18:22:31" in linha
        assert "inicio" in linha
        assert "backend" in linha
        assert "T-014" in linha
        assert "motor de ToolInstance" in linha

    def test_evento_incompleto_nao_quebra_a_formatacao(self) -> None:
        # Um evento antigo pode nao ter todos os campos de hoje.
        assert formatar_eventos.formatar({}) is not None

    @pytest.mark.parametrize("acao", ["inicio", "fim", "revisao"])
    def test_cada_acao_tem_cor_propria(self, acao: str) -> None:
        assert formatar_eventos.CORES[acao] in formatar_eventos.formatar({"acao": acao})


class TestEntradaPadrao:
    def test_linha_invalida_e_pulada_sem_derrubar_o_monitor(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        entrada = "{pela metade\n" + json.dumps({"acao": "fim", "papel": "qa"}) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(entrada))
        assert formatar_eventos.main() == 0
        saida = capsys.readouterr().out
        assert saida.count("\n") == 1
        assert "qa" in saida

    def test_linha_json_que_nao_e_objeto_e_ignorada(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("[1, 2, 3]\n"))
        assert formatar_eventos.main() == 0
        assert capsys.readouterr().out == ""
