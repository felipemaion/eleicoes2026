# Handoff backend — T-B23 (erro_transitorio e coleta parcial)

Branch `fix/backend-status-redes-novos` (sobre `origin/main`); 2 commits: `test:` vermelho, `fix:` verde.

## O que fez
- `StatusRede` (`servicos/redes.py`) aceita `erro_transitorio`; descrições em `redes_perfis.py` e
  `redes_correlacoes.py` atualizadas. `Excluidos.indisponivel` também conta `erro_transitorio` sem dados.
- `RedesStatus.perfis_com_erro` (0 se o `status.json` for antigo); `ColetaRedes` ganha `perfis_com_erro`.
- Decisão (`redes_coleta.py`): `ultima_ok`/`coletado_em` avançam com `ok` **e** `parcial`
  (`COLETAS_QUE_GRAVAM`), pois `parcial` grava snapshots; `resultado` e `perfis_com_erro` seguem
  expostos no `/api/health` para o aviso. `limite`/`erro` continuam não contando.
- OpenAPI regenerado (`make openapi`): novo campo `perfis_com_erro` em `ColetaRedes`.
- Teste: `apps/api/tests/test_b23_redes_novos_status.py` (DuckDB real; perfil `erro_transitorio` →
  `/redes`, `/redes/correlacoes`, `/redes/serie` 200; health `parcial`; status antigo).

## Pendências / avisos
- Não editei `packages/contratos` (a T-D15 já inclui `erro_transitorio` em `STATUS_PERFIL`).
- Frontend: tipos gerados mudam (`ColetaRedes.perfis_com_erro`, status `erro_transitorio`); UI do aviso é a seguir.
- Teste foi escrito com status trocado por polars na fixture, pois a fixture oficial ainda não tem o caso.

## Como verificar
`cd apps/api && uv run pytest` (362 passed) · `make lint` · `make openapi && git diff --exit-code docs/api`
