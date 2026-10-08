# Handoff — analise T-A07 (classificação de receitas com rótulos 2022 e 2026)

Branch `fix/analise-rotulos-receita` (a partir de `origin/main`). Commits: `test:` (vermelho) → `fix:` → este handoff.

## O que foi feito
- Levantei as **47 combinações reais** fonte × origem × natureza (sem as linhas nulas de R$ 0,00) no
  Parquet do ETL (`.worktrees/dados/data/processed/receitas_candidatos`, dt_geracao 2022 = 2026-10-04,
  2026 = 2026-10-07). Copiadas como fixture: `packages/indicadores/tests/fixtures/rotulos_receita_2022_2026.json`,
  com `categoria_esperada` por linha. Só rótulos e contagens, nenhum dado pessoal.
- `financeiro.classificar_receitas` agora cobre 100% delas. "Rótulo desconhecido falha" continua valendo,
  inclusive para fonte nula.
  - Novas origens: "Fundo Especial de Financiamento de Campanha" → `fefc`, "Fundo Partidário" →
    `fundo_partidario`, "Doações para Campanha" → `outros_candidatos` (2026); "Comercialização de Bens com
    OR/FEFC" → `outros` (2022). Removi "Comercialização de bens ou realização de eventos", que não aparece
    nos dados.
- **Bug achado e corrigido:** o TSE grava a natureza como **"ESTIMÁVEL"**, mas a biblioteca só aceitava
  "ESTIMADO", então `resumo_receitas` falhava com dado real. Agora aceita "ESTIMÁVEL" e mantém "ESTIMADO"
  como sinônimo, para não quebrar a view da API.
- Spec §4.1 atualizada (tabela, decisão e magnitude). Vetor `receitas.json` passou para a **versão 2**:
  natureza "ESTIMÁVEL" no caso c1 e novo caso `c2_rotulos_exclusivos_2022_e_2026`.

## Decisão metodológica (registrada na spec, sem ADR por ser de magnitude desprezível)
No CSV bruto, as origens 2026 de códigos 10030201/02/03 (82 lançamentos) têm sempre um outro candidato como
doador (CNPJ de campanha, CNAE de organização política, `SQ_CANDIDATO_DOADOR` preenchido). São repasses entre
candidatos detalhados pela origem do dinheiro, e chegam com fonte "Outros Recursos".
- Quando a origem nomeia um fundo, conta como recurso público. É coerente com a regra "fonte manda" para os
  repasses que já chegam com fonte FEFC.
- O impacto é de R$ 159 mil de FEFC + R$ 5,6 mil de FP, menos de 0,01% do FEFC.
- A outra leitura possível seria tratar tudo como `outros_candidatos`. Ela mudaria `pct_publico` só na casa
  decimal, e apenas para os poucos candidatos envolvidos.

## Pendências / para outros papéis
- **backend:** o `CASE 'ESTIMÁVEL' → 'ESTIMADO'` em `apps/api/src/api/repositorio/duckdb.py:82-85` pode ser
  removido, porque a biblioteca aceita o rótulo real. Não é urgente, já que o sinônimo continua aceito.
  Se algum teste do backend consome `receitas.json`, ele precisa aceitar a versão 2 (novo caso c2).
- **dados:** em `docs/fontes-de-dados.md` (§valores distintos), a frase "a *origem* repete o nome de um fundo"
  pode ganhar a explicação dos códigos 1003020x (doador = outro candidato). Opcional.
- `make lint`/`make test` da parte web falham neste worktree por falta de `node_modules` (ambiente). Python
  (ruff, mypy --strict, pytest) está verde: 471 testes, `financeiro.py` com 98% de cobertura.

## Como verificar
```bash
uv run pytest packages/indicadores/tests/test_financeiro.py packages/indicadores/tests/test_vetores_impl.py -q
uv run ruff check . && uv run mypy --strict packages/indicadores
```
