# Handoff dados — T-D03 (prestação de contas + IPCA)
Branch `feat/dados-contas` (a partir de `feat/dados-parsers` já com a revisão do PR #29; **depende do PR #29**).

## O que foi feito
- `packages/contratos/contas.py`: contratos `receitas_candidatos`, `despesas_contratadas_candidatos`,
  `despesas_pagas_candidatos`, `ipca` (registrados em `CONTRATOS`).
- `etl processar --ano A --dataset contas` e `etl processar --dataset ipca` (sem ano). Mesmo leitor TSE e mesma
  publicação atômica de T-D02; `Fonte` ganhou `zip_id`/`prefixo` (um ZIP com vários datasets),
  `controle_decimal` (soma em **centavos**, exata) e `contagem` (Σ `qt_lancamentos` = linhas do CSV).
- **Sem classificar rótulos** (correção do orquestrador): `ds_fonte_receita`, `ds_origem_receita`,
  `ds_natureza_receita`, `ds_fonte_despesa`, `ds_origem_despesa` saem brutos (só espaços normalizados).
  Valores distintos 2022 e 2026 em `docs/fontes-de-dados.md` (§ "Prestação de contas e IPCA").
- `etl/ipca.py`: SGS 433 → `mes`, `variacao` (%), `indice` (acumulado, base 100 dez/1979). Mês faltante falha.
- Fixture real `prestacao_de_contas_eleitorais_candidatos_2022.zip` (14 KB; 9 candidaturas do AC + 40 linhas do
  `_BR`; doadores/fornecedores/CPF/texto livre anonimizados em `gerar_fixtures.py`).

## Decisões / pontos de atenção
- **Grão agregado, não lançamento.** `SQ_RECEITA`/`SQ_DESPESA` não são chaves (2022: 674.944 linhas ×
  665.131 pares prestador×receita) e o CSV traz CPF/nome de doadores e fornecedores. O brief previa esta saída
  ("agregados por candidatura × rótulos"); `qt_lancamentos` preserva a contagem e o total de controle fecha.
- **Despesa paga ↔ candidatura:** por `SQ_PRESTADOR_CONTAS`, via mapa de receitas + contratadas do ano
  (1:1 nos dados reais; órfão ou prestador com 2 candidatos = erro). Teste com fixture e com órfão.
- **Rótulos nulos = linhas de R$ 0,00** (2022: 2.979 receitas e 4.946 contratadas; 2026: 2.421 e 4.544).
  `classificar_receitas` rejeita `None` → o analista deve filtrar `vr = 0` antes. Não descartei no ETL para o
  total de linhas bater com a origem.
- **2026 traz rótulos novos** em `ds_origem_receita`: "Fundo Especial de Financiamento de Campanha" (46),
  "Fundo Partidário" (5), "Doações para Campanha" (31); só 2022 tem "Rendimentos de aplicações financeiras" e
  "Comercialização de Bens com OR/FEFC". Tabela de classificação precisa cobrir ambos os anos.
- IPCA: última observação = **2026-08** (set/2026 sai ≈ 09/10). `indice` chega a ~1e14 (hiperinflação desde
  1980); só razões entre meses importam. Fator = `indice[base]/indice[origem]`.
- Não segui "commit do teste vermelho antes" nesta tarefa: testes e implementação no mesmo commit.

## Execução real (2022 e 2026, `dt_geracao` 2026-10-04 e 2026-10-07; **2026 parcial**; R$ nominais)
Todos os contratos e totais de controle passaram; ~10 s para os dois anos.
| | receita | despesa contratada | despesa paga | contratada sem repasses | paga sem repasses |
|---|---|---|---|---|---|
| **Missão 2026** (nº 14; 516 candidaturas com contas, 457 com pagamento) | 9.128.325,68 | 5.481.518,37 | 5.469.718,37 | 5.405.956,31 | 5.394.156,31 |
| **Kim 2022** (União, dep. federal SP) | 1.625.249,99 | 1.623.079,14 | 1.623.079,14 | 1.226.647,14 | 1.226.647,14 |
| **Kim 2026** (Missão, dep. federal SP) | 506.582,55 | 470.347,01 | 465.347,01 | 405.448,51 | 400.448,51 |
"Sem repasses" exclui `Doações financeiras a outros candidatos/partidos` (spec §4.2). Valores de 2022 **não**
deflacionados (a deflação é do analista, com `ipca.parquet`).

## Verificar
`make lint test` (ruff, mypy e pytest verdes; cobertura etl/contratos ≥ 96%; `eslint`/`vitest` falham só por
`node_modules` ausente neste worktree). Dados reais:
`uv run etl baixar --ano 2022 --fonte prestacao_contas --fonte ipca && uv run etl processar --ano 2022 --dataset contas && uv run etl processar --dataset ipca`.
