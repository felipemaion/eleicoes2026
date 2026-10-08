# Handoff — analise · T-A06 (revisão de `indicadores` + constantes do contrato)

Branch `fix/analise-indicadores-revisao`, rebaseada em `origin/main` (3b0389d, com T-A05 #33 e
contratos #29). Commits `test:` → `feat:`/`fix:`/`refactor:`.

## O que foi feito
0. **`espacial.quebras_comuns(valores_por_ano, k=5, excluir_n_baixo=True, coluna="valor") -> list[float]`**
   — spec nova **§8.3** (`indicadores.md#quebras-comuns`) + vetor `vetores/quebras_comuns.json`
   (12 casos, gerado por referência independente em Python puro) + texto público em
   `publico/textos.json`.
   - Entrada: `{ano: DataFrame}` com `valor` e `n_baixo` (este só se `excluir_n_baixo`).
   - Conjunto pooled dos anos, sem `null` e sem `n_baixo`; quantis `j/k` lineares (tipo 7);
     2 algarismos significativos, meio para cima (sobe até 6 se fundir quantis distintos);
     limiares únicos em `(min, max]`. Saída: lista estritamente crescente de **até** `k−1`
     limiares para `d3.scaleThreshold` (classes `[b_j, b_j+1)`); com empates (muitos zeros) vêm
     menos limiares — a legenda usa `len + 1` classes.
   - Falha alto: `k < 2`, nenhum ano, coluna ausente, `n_baixo` nulo, NaN/inf, menos de `2k`
     valores ("poucos valores"), nenhum limiar ("sem variação").
   - Backend (T-B02): uma chamada por indicador × cargo × recorte, mesmas quebras em 2022 e 2026.
1. `desempenho.votos_nominais` recusa `nr_turno`/`cd_cargo` com mais de um valor, **salvo** se a
   coluna estiver nas `chaves` (aí não soma). `_exigir_unico` virou `_comum.exigir_valor_unico`.
2. `financeiro.custo_por_voto` e `custo_por_voto_agregado`: `despesa_paga` nula com contratada
   não nula = **0** (sem linha em `despesas_pagas` = nada pago); sem contas segue nulo.
3. `evolucao.evolucao(..., *, cd_cargo)` — **obrigatório, keyword-only**; Senado
   (`CD_CARGO_SENADOR = 5`) → `ValueError`. Docstring documenta: AMC num ano só → colunas do
   outro ano e **todas** as diferenças nulas (ausência ≠ zero). Vetor `evolucao` v2 (entrada com
   `cd_cargo` + caso `senado_recusado`). Nenhum chamador fora do pacote (grep em `apps/`).
4. `indicadores/_colunas.py`: nomes de colunas do TSE de votação/candidatura conferidos contra
   `contratos.tse` no import (falha alto se o contrato renomear). `desempenho` e `grupos` usam as
   constantes.

Decisões registradas em `indicadores.md` §8-A (bullet "Revisão (T-A06)").

## Pendências
- `contratos` não exporta constantes de nome: hoje validamos literais contra `Contrato.colunas`.
  Se o `dados` publicar constantes, trocar `_colunas._de(...)` por elas.
- Colunas financeiras (`ds_fonte_receita`, `ds_origem_*`, `vr_receita`…) seguem literais: não há
  contrato de receitas/despesas na main.
- `packages/etl/tests/test_processar.py::test_cpf_nunca_toca_processed` falhou uma vez na suíte
  completa (`FileNotFoundError` num CSV temporário) e passou sozinho: parece intermitente
  (território do `dados`, não tocado aqui).

## Como verificar
```bash
uv run pytest -q packages/indicadores/tests --cov=indicadores   # 99 %, espacial 100 %
uv run ruff check . && uv run mypy --strict packages/indicadores
```
