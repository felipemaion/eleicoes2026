# Handoff dados — T-D11 (situação da candidatura e foi_as_urnas)
Branch `feat/dados-situacao-candidatura` (a partir de origin/main).

## O que mudou
- `etl/situacao.py::foi_as_urnas()` (regra única) → coluna `foi_as_urnas: bool` (obrigatória, não nula) em
  `consulta_cand` (contrato em `contratos/tse.py`), aplicada em `processar._consulta_cand` após o `pessoa_id`.
- Testes: `test_situacao.py` (apto eleito, apto sem voto, substituído, cancelado, indeferido com voto) e
  `test_processar.py::test_consulta_cand_traz_foi_as_urnas…` (fixture, contrato, coerência). Docs em `fontes-de-dados.md`.
- `data/processed/consulta_cand` 2022 e 2026 reprocessados localmente (28 arquivos cada).

## DESVIO DO BRIEF (importante p/ T-B21)
O brief pedia carregar `CD/DS_DETALHE_SITUACAO_CAND` e preencher `situacao`. **Não é possível pela fonte oficial:**
o CSV não tem a coluna DETALHE nem situação no dia da eleição, e `DS_SITUACAO_CANDIDATURA` é `#NE` em 100% de 2026.
Não inventei situação: `ds_situacao_candidatura` continua nula em 2026 (a API segue com `situacao=null`).
O discriminador viável é `foi_as_urnas` (= tem `CD_SIT_TOT_TURNO`). Se quiserem a situação cadastral de 2026,
exigiria outra fonte oficial (ex.: DivulgaCand/ `consulta_cand` futuro) — decisão do orquestrador.
O backend (T-B21) deve filtrar/contar por `foi_as_urnas`, não por `situacao`; precisa incluir a coluna na
leitura do repositório (`apps/api/.../duckdb.py` lista colunas explícitas — fora do meu território).

## Medidas (consulta_cand local)
Registros que NÃO foram às urnas: **2022 = 1.662 de 29.322; 2026 = 1.069 de 20.989**.
Por cargo (2022 / 2026): 1º suplente 46/41 · 2º suplente 49/42 · dep. distrital 22/15 · dep. estadual 835/518 ·
dep. federal 660/410 · governador 6/10 · presidente 2/1 · senador 16/11 · vice-gov. 24/20 · vice-pres. 2/1.

**Missão 2026** (registros / não foram às urnas / pessoas): 1º suplente 6/1/5 · 2º suplente 6/1/5 · dep. distrital
14/1/14 · dep. estadual 161/6/161 · dep. federal 334/15/334 · governador 9/0/9 · presidente 1/0/1 · senador 6/1/5 ·
vice-gov. 9/0/9 · vice-pres. 1/0/1. (Senador 6 registros para 5 pessoas = o caso Guto; suplentes 1º/2º idem.)

Pessoas com 2+ registros no mesmo cargo/ano (qualquer turno): 2022 = 165 pessoas·cargo; 2026 = 25
(22 com 1 registro na urna, 3 sem nenhum). 2026: nenhuma pessoa tem 2 registros *na urna* no mesmo cargo.
2022: 55 pessoas·cargo com 2 na urna (candidatos que foram a 2º turno, registro por turno).
No Missão: 3 casos em 2026 (senador, 1º e 2º suplente) — todos com exatamente 1 na urna — e vice-gov. 2022 (2º turno).

## Verificar
`PESSOA_ID_SAL=… uv run etl processar --ano 2026 --fonte consulta_cand`; `uv run pytest packages -q` verde;
ruff/format ok; mypy --strict tem 11 erros **preexistentes** em tests/ (test_geo, test_download), nenhum nos arquivos tocados.
`make lint` falha só no eslint (sem node_modules neste worktree).
