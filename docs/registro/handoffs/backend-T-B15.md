# Handoff backend — T-B15 (comparativo por lado + n_para)

## O que foi feito
- `/api/comparativo` ganhou `grupo_2022` e `grupo_2026`. Cada lado é um grupo **ou** candidatos
  (`sq_2022`/`sq_2026`, ou `pessoas`, que preenche os dois lados). Os lados são independentes e
  podem ser misturados, nos dois sentidos. `comparacao` continua como atalho (modo antigo intacto).
- 422 com código: `lado_vazio`, `lado_ambiguo` (grupo e candidatos no mesmo lado, inclusive com
  `pessoas`), `grupo_ano_errado`, `grupo_desconhecido`, `comparacao_e_selecao` (comparacao + qualquer
  lado), `comparativo_sem_alvo`, `sem_par_comparavel`. `sq` inexistente → 404.
- `rotulo` gerado: "Kim + Beraldo (2022) → Partido Missão 2026" (até 3 nomes, depois "+N"). Em
  seleção pura deixou de ser "Seleção do usuário"; `comparacao` segue "selecao" e `de.id`/`para.id`
  são `selecao` no lado de candidatos, o id do grupo no lado de grupo.
- **Bug `n_para`:** 2026 chega com `ds_situacao_candidatura` nulo e `_n_aptas` devolvia `null`.
  Agora conta APTAS + candidaturas ainda sem situação (indeferida/renunciada, que já têm situação,
  ficam fora). `n_de`/`n_para` deixam de ser nuláveis no OpenAPI (`int`).
- `mesmos_candidatos` só é forçado a `false` quando os dois lados são seleção; em lado misto vale.
- Receitas e `municipios` não mudaram: funcionam para qualquer combinação.
- `varredura.py`: casos mistos (candidato × grupo nos dois sentidos, e grupo × grupo por lado).
- OpenAPI regenerado (`make openapi`).

## Decisões
- Reaproveitei `_selecao` para os lados de candidatos; `_por_lados` só valida a combinação.
- Teste antigo `test_n_aptas_nulo_...` (test_quebras_comuns) afirmava `n_para is None` de propósito;
  foi trocado por `== 1`, conforme o brief (era o bug).

## Para o frontend (T-W20)
- `n_de`/`n_para` agora sempre inteiros. Parâmetros novos `grupo_2022`/`grupo_2026`; só adição.

## Como verificar
`uv run pytest apps/api -q` (inclui `tests/test_b15_lados.py`), `make lint` (parte Python verde; o
eslint do web falha só por falta de `node_modules` neste worktree), `make openapi` sem diff.
Ex.: `/api/comparativo?cargo=DEPUTADO FEDERAL&uf=SP&sq_2022=1&sq_2022=9&grupo_2026=missao_2026`.

## Pendências
Nenhuma. Nota: `mypy apps/api/scripts` acusa erros antigos em `gerar_fixture.py` (fora do `make lint`).
