# Handoff — analise T-A08 (indicadores de receita: spec + biblioteca)

Branch `feat/analise-receitas` (a partir de `origin/main` @ deb0686). Commits: `test:` (spec + vetores +
testes vermelhos) → `feat:` (lib) → `docs:` (textos públicos) → este handoff.

## O que foi feito
- **Spec** `docs/metodologia/indicadores.md` §4.4–4.10 (nova): conjunto proposto com justificativa (tabela
  em §4.4) e, para cada indicador, fórmula, denominador, unidade, recorte, limitações e referência. Refs
  novas: Hirschman (HHI), Lei 9.504/1997 art. 23 §4º IV, Res. TSE 23.607/2019.
- **Vetores** gerados por implementação de referência independente (Python puro):
  `receitas.json` passou para a **v3** e há 5 novos: `receitas_grupo`, `receita_por_voto`, `saldo_campanha`,
  `distribuicao_receita` e `comparacao_receitas`.
- **Lib** `indicadores.financeiro`, com 100% de cobertura:
  - `resumo_receitas` ganhou colunas novas. As existentes não mudaram.
    - `receita_estimavel`, `receita_repasses_candidatos`, `receita_sem_repasses`.
    - `pct_pessoa_fisica` (pessoa física + financiamento coletivo), `pct_estimavel`.
    - `hhi_fontes` e `n_efetivo_fontes`.
    - `vr_receita` negativa agora **falha**. Não há nenhuma nos dados de 2022 e 2026.
  - Funções novas: `receita_por_voto`, `receita_por_voto_agregado` (Σ/Σ + mediana + excluídos),
    `receita_por_mil_aptos`, `saldo_campanha`, `distribuicao_receita` e `comparar_receitas`.
    - `comparar_receitas` aplica o IPCA dentro da função; o chamador passa 2022 **nominal**.
  - Outras adições: `expr_repasse_candidato`, `ORIGENS_REPASSE_CANDIDATO` e
    `despesa_campanha(…, incluir_transferencias=True)`, que dá a despesa usada no saldo.
- **Textos públicos** (`docs/metodologia/publico/textos.json`):
  - 10 indicadores novos: pct_pessoa_fisica, receitas_estimaveis, concentracao_fontes, receitas_grupo,
    receita_por_voto, receita_por_mil_aptos, saldo_campanha, pct_receita_gasta, distribuicao_receita,
    comparacao_receitas. Todos estão na tela `gastos`.
  - Também: aviso `repasses_grupo`, 2 termos novos no glossário e o `cuidado` de `receitas` corrigido.

## Bug corrigido (afeta números publicados do grupo)
`grupos.receitas_grupo` só descontava repasses internos na categoria `outros_candidatos`. Mas o FEFC
repassado por outro candidato chega com **fonte FEFC** e cai em `fefc`, então escapava da deduplicação.
Em 2022 são R$ 162 mi de FEFC e R$ 6,7 mi de FP repassados entre candidatos, contra R$ 28,8 mi em Outros
Recursos. Agora o repasse é reconhecido pela **origem**. A função também devolve
`receita_repasses_internos` e `receita_repasses_doador_desconhecido`. A assinatura não mudou e a API
continua verde.

## Pendências / para outros papéis (decisão do orquestrador)
- **dados (importante):** o contrato `receitas_candidatos` não guarda `sq_candidato_doador`.
  - Hoje a API passa `NULL::BIGINT`, então **nenhum repasse interno é descontado**. Todo repasse aparece em
    `receita_repasses_doador_desconhecido`: fica visível, mas o total do grupo é o bruto.
  - Pedido: incluir `SQ_CANDIDATO_DOADOR` na chave de agregação das receitas. É identificador de
    candidatura, não dado pessoal. A spec §7 já marca a coluna.
- **backend:** expor os novos campos no `/contas`:
  - Do `resumo_receitas`, os campos novos.
  - `receita_por_voto_agregado`, `distribuicao_receita` e `saldo_campanha`. No saldo, usar despesas com
    `incluir_transferencias=True`.
  - `receita_por_mil_aptos`, com os aptos da UF contados uma vez.
  - A faixa `[total − desconhecido, total]` da receita do grupo.
  - Na Evolução, `comparar_receitas` com 2022 nominal.
  - Os testes do backend que consomem `receitas.json` precisam aceitar a v3, que tem casos novos (c3, c4 e
    `valor_negativo_falha`).
- **frontend:** os textos já estão em `textos.json`, e o aviso `repasses_grupo` entrou em `telas.gastos`.
  Receita por voto e por mil aptos usam escala log. Receita nunca vai para o mapa (não é espacial).
- Ambiente: o `make lint test` da parte web falha neste worktree por falta de `node_modules`. O Python está
  verde: 605 testes, incluindo os da API.

## Conferência com dado real (Parquet do ETL, 07/10/2026; só agregados)
- Brasil: 2022 tem R$ 6,64 bi de receita, 81,4% pública e N efetivo de fontes de 1,76. 2026 (parcial) tem
  R$ 6,49 bi, 84,2% pública e N efetivo de 1,69.
- Missão 2026: 490 candidatos com contas e R$ 9,13 mi no total. A média é de R$ 18,6 mil e a mediana de
  R$ 5,7 mil, porque a cauda é pesada. São 35,9% públicos, e R$ 64,9 mil de repasses têm doador
  desconhecido.

## Como verificar
```bash
uv run pytest packages/indicadores -q --cov=indicadores --cov-report=term
uv run pytest apps/api -q
uv run ruff check . && uv run mypy --strict packages/indicadores
```
