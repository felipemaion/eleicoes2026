# Handoff — backend T-B14 (API de receitas)

Branch `feat/backend-receitas`, criada a partir de `origin/feat/analise-receitas` (T-A08, PR #73): **rebase na
main quando o #73 entrar**. Commits: `test:` vermelho → `feat:`.

## O que foi feito
Sem fórmula local: tudo vem de `indicadores.financeiro` / `grupos`. Contrato mudou só por **adição** de campos.
- **`/api/gastos`** (grupo): `receitas` ganhou receita_estimavel, repasses (candidatos, internos, doador
  desconhecido), `faixa_receita {minima, maxima}`, pct_pessoa_fisica, pct_estimavel, hhi_fontes,
  n_efetivo_fontes. Novos: `receita_por_voto` (Σ/Σ + mediana + excluídos), `distribuicao_receita`
  (média/mediana/p25/p75/máx), `saldo`, `receita_por_mil_aptos` e `aptos`.
- **`por_candidato`** e **ficha** (`gastos`): receita_por_voto, receita_por_mil_aptos, saldo_contratado,
  saldo_financeiro, pct_receita_gasta (+ no `/gastos`: pct_pessoa_fisica, n_efetivo_fontes, repasses).
- **`/api/comparativo`**: novo `receitas` (null se não é 2022→2026 ou um lado não tem contas) com
  `monetarios`/`percentuais`; cada indicador traz `de_nominal`, `de` (2022 no mês-base), `para`, `delta`,
  `var_pct`; `base_ipca` e selos `contas_parciais_*`. Usa `comparar_receitas` com 2022 **nominal**
  (`contas_de(..., nominal=True)`), sem corrigir duas vezes. Vale também para a seleção do usuário.
- `fontes` do comparativo inclui `prestacao_contas` e `ipca`; texto da fonte atualizado.
- `docs/api/openapi.json` regenerado. Testes: `apps/api/tests/test_b14_receitas.py` (DuckDB real).

## Decisões
- Métricas **do grupo** (receita por voto, distribuição, por mil aptos) usam a receita **líquida de repasses
  internos**, a mesma de `receitas.receita_total`. Métricas **por candidato** usam a receita bruta.
- **Saldo** usa receita bruta e despesa **com** repasses (spec §4.8): repasses internos se anulam.
- `receita_por_mil_aptos` do grupo só com **um cargo** (eleitorados de cargos diferentes não se somam); senão
  `null`. Aptos contados uma vez por circunscrição (`BasesPorEscopo`; `BR` = Brasil).
- Receita não vai ao mapa (não é espacial).

## Pendências
- **dados:** `sq_candidato_doador` já chega do repositório; conferir em produção que o Parquet o preserva
  (senão todo repasse cai em "doador desconhecido", visível na faixa).
- **frontend:** consumir os campos novos (textos em `textos.json`); regenerar tipos do OpenAPI.
- `mypy --strict` nos testes tem erros antigos (não tocados); `apps/api/src` está limpo.
- Varredura: `varredura.py` já cobre `/gastos` e `/comparativo`; rodar contra produção após o deploy.

## Como verificar
```bash
uv run pytest apps/api -q && uv run ruff check . && uv run mypy --strict apps/api/src && make openapi && git diff --exit-code docs/api
```
