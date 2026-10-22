# Handoff dados — T-D13 (status.json em qualquer exceção da coleta)

**Branch:** `fix/dados-status-qualquer-excecao` · `test:` vermelho → `fix:`.

## O que foi feito
- `etl/redes/servidor.py::executar`: `except Exception` após o `except (ErroMeta, ContratoViolado, OSError)`
  grava `status.json` com `resultado: "erro"` e `motivo` = `Tipo: mensagem` (truncado a 300 caracteres),
  apaga `.novo/` e **relança**. A série anterior fica intacta (promoção só no sucesso).
- Acréscimo do orquestrador: se gravar o status de erro também falhar, a segunda falha é logada em stderr
  e a exceção **original** é a que propaga.
- Testes em `test_redes_servidor.py`: `KeyError` no meio da coleta (status, série preservada, `.novo` removido,
  exceção propagada) e falha ao gravar status (original relançada, log em stderr).

## Limites (inalterados)
OOM-kill e falhas antes do processo (pull da imagem, volume) continuam cobertos só pelo `OnFailure` do
systemd (`data/redes-ultima-falha.txt`) — não geram `status.json`.

## Verificar
`uv run pytest packages/etl/tests/test_redes_servidor.py` · `make lint test`: pytest 950 ok, ruff ok.
O mypy acusa 11 erros preexistentes em outros arquivos de teste (nenhum em servidor); o `pnpm test` do web
falha por `node_modules` ausente neste worktree.

## Pendência
A imagem nova sai pelo workflow `imagem-etl` no merge. O brief `docs/tarefas/T-D13.md` não estava legível
no checkout principal ao retomar; segui a mensagem do orquestrador para o acréscimo.
