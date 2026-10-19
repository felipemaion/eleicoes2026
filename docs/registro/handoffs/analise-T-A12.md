# Handoff analise — T-A12 (razão despesa ÷ receita financeira + alerta de declaração)

Branch `feat/analise-razao-gasto` (a partir de `origin/main` 79da584). Commits: `test:` (spec §4.11 +
vetor + testes vermelhos) → `feat:` (implementação + texto público) → `docs:` (este handoff).

## O que foi feito
- **Spec §4.11** (`docs/metodologia/indicadores.md#razao-gasto`): fórmula, denominador, numerador,
  limites 70/110 % com justificativa empírica, nulos, leitura do alerta, limitações e os três casos
  reais. Linha nova no índice da §4.4 e nota na §4.8 sobre `pct_receita_gasta`.
- **Vetor** `docs/metodologia/vetores/razao_gasto.json`: limites inclusivos (0,70 e 1,10 não
  alertam; 0,69999 e 1,10001 alertam), nulos (receita financeira 0, nula, despesa contratada nula,
  paga nula → 0) e Renan / Cury / Caiado (2026, ZIP de 14/10).
- **Código** `financeiro.razao_gasto(df)` (polars→polars, sem I/O) + `LIMITE_INFERIOR_GASTO`,
  `LIMITE_SUPERIOR_GASTO`. Entrada: `receita_financeira`, `despesa_contratada`, `despesa_paga`.
  Saída acrescenta `razao_gasto_contratada`, `razao_gasto_paga` (Float64, **fração**),
  `alerta_declaracao` (Boolean) e `sentido_alerta` (`"abaixo"`/`"acima"`/null).
- **Texto público** `razao_gasto` em `docs/metodologia/publico/textos.json`, incluído na tela `gastos`.
- Cobertura de `financeiro.py`: 100 %.

## Decisões
1. **`pct_receita_gasta` fica** (a ficha atual o usa), com nota na §4.8 dizendo que mede outra coisa
   (receita total no denominador). Nada da API/web quebra.
2. **Numerador inclui repasses** (`despesa_campanha(…, incluir_transferencias=True)`), como o saldo:
   para conferir a declaração importa o que saiu da conta. Os números do T-D12 são somas brutas, logo
   já seguem essa regra.
3. **Razão em fração**, não em %: a comparação com 0,70/1,10 fica exata nos limites (divisão
   arredondada corretamente = literal). A interface multiplica por 100.
4. **Não avaliável → `alerta_declaracao = null`** (não `False`), para receita financeira 0/nula ou
   sem despesa contratada: "sem alerta" sem afirmar que a conta está ok. Dentro da faixa é `False`.
5. **`sentido_alerta`** acrescentado (fora da letra do brief, barato): "abaixo" e "acima" têm leituras
   diferentes (declaração incompleta × dívida) e a tela precisa saber qual texto mostrar.
6. **Justificativa dos limites** (medida no Parquet processado, worktree `dados`): 2022 final,
   N = 23.157 com receita financeira > 0 — mediana 1,000; 88,7 % entre 0,95 e 1,05; 3,2 % < 0,70 e
   3,7 % > 1,10. 2026 parcial (14/10, N = 16.179): mediana 0,67, 53 % < 0,70, 5,6 % > 1,10.

## Pendências / para o backend (resto do item (c) da T-B21)
- Chamar `razao_gasto` sobre o mesmo DataFrame do `saldo_campanha` (despesas **com** repasses;
  `receita_financeira` de `resumo_receitas`). Expor as 4 colunas na ficha; `alerta_declaracao` null ≠ false.
- Em 2026 parcial o alerta "abaixo" vai disparar para ~metade das candidaturas: mostrar **sempre**
  com o selo "contas parciais". Se o backend souber o tipo de prestação (parcial × final) por
  candidato, vale considerar destacar o alerta só para quem entregou a final — decisão de produto,
  não tomei.
- Agregado de grupo não implementado (spec diz Σ/Σ se precisar).

## Como verificar
```bash
uv run pytest -q packages/indicadores -k razao_gasto
uv run pytest -q packages/indicadores --cov=indicadores.financeiro --cov-report=term-missing
make lint test
```
