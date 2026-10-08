# Fluxo de trabalho

## TDD (vermelho → verde → refatora)
1. Ler o brief e a spec (metodologia/contrato).
2. Escrever o teste que expressa o critério de aceite; rodar e **ver falhar pelo motivo certo**.
3. Commit `test(<escopo>): …` (vermelho) quando a tarefa introduz comportamento novo.
4. Implementar o mínimo para passar; commit `feat(<escopo>): …`.
5. Refatorar com testes verdes; `make lint test`.

Pirâmide: unidade (maioria, sem I/O) → integração (DuckDB real sobre fixtures Parquet; API com
httpx) → E2E Playwright (fluxos principais). Cobertura ≥ 80% por pacote.

## Git e GitHub
- Branch por feature: `feat/<papel>-<slug>`, a partir de `origin/main` atualizada.
- Conventional Commits em português. Autor: Felipe. **Sem** `Co-Authored-By` de IA (hook).
- Uma Issue por tarefa (`T-xxx` no título), com labels de papel e fase. PR com `Closes #N`,
  resumo, como testar, checklist.
- Merge **squash** pelo orquestrador após CI verde e revisão.
- Antes de entregar: `git fetch && git rebase origin/main`. Conflito em `uv.lock` ou
  `pnpm-lock.yaml`: aceite a versão da main e regenere (`uv lock` / `pnpm install`) — nunca edite
  lockfile à mão.
- Dependência nova num pacote: `uv add --package <pacote> <dep>` (o workspace é um só).

## Gate de PR (orquestrador)
1. Ler o handoff e o diff.
2. Rodar revisores por linguagem (subagentes) e corrigir/devolver achados bloqueantes.
3. `make lint test` local verde; push; abrir PR; CI verde; merge.
4. Atualizar `docs/registro/decisoes.md` se houve decisão; ADR se for estrutural.

## Definição de pronto
- Critério de aceite do brief atendido e testado.
- Lint, tipos e testes verdes; cobertura mantida.
- Documentação atualizada (docstrings, docs/ afetados, OpenAPI se API).
- Handoff escrito.
