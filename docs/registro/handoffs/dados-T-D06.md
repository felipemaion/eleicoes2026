# Handoff dados — T-D06 (pessoa_id com sal único + lista MBL reproduzível)

Branch `fix/dados-pessoa-id` (a partir de `origin/main`), 2 commits + este.

## O que foi feito
1. **Reprocessado** `consulta_cand` 2022 e 2026 com o `PESSOA_ID_SAL` de `/Users/maion/Projects/Eleicoes2026/.env`
   (único dataset com `pessoa_id`; nenhum outro carrega a coluna). Impressão do sal: `cad50fc3fe9e` nos dois anos.
2. **Guarda**: `Entrada.sal_impressao` no manifesto (`sha256(sal)[:12]`, nunca o sal);
   `processar_fonte` falha **antes de escrever** (`ErroProcessamento`) se outro ano do mesmo dataset tem
   impressão diferente. Testes em `test_processar.py` (3).
3. **Critério MBL** em `etl/lista_mbl.py::candidaturas_mbl_2022(cand, indicados)`: pessoas do Missão 2026
   (nr_partido 14) + pessoas dos 4 indicados (`sq_candidato` manual) → candidaturas de 2022, uma por pessoa.
   Regressão (`test_lista_mbl.py`, sobre `data/processed`; pula se ausente) devolve **exatamente os 18
   `sq_candidato`** de `data/reference/mbl_2022.csv`.

## Decisão de método
Duas pessoas tiveram 2 registros em 2022 (Visoli: federal INAPTO + estadual; Beraldo: federal + estadual INAPTO).
Regra: vale o registro com `ds_sit_tot_turno` preenchido (resultado de urna). Bate com a referência manual.
Os 4 indicados não são deriváveis do dado (Beraldo está no PP em 2026): continuam entrada manual.

## Interseção 2022×2026 (pessoa_id, antes: 0)
- Total (todos os partidos): **6.393 pessoas**.
- Missão 2026 que disputaram 2022: 17 pessoas / 18 candidaturas 2022 (543 pessoas Missão com pessoa_id).

## Verificar
`uv run pytest packages -q` (verde). Mypy: 10 erros preexistentes só em `test_geo.py`/`test_download.py`, não tocados.

## Pendência para o orquestrador
Dados locais prontos em `data/processed/consulta_cand` **deste worktree** (`.worktrees/dados/data`; o
manifesto em `data/raw/manifesto.json` também). Se a publicação sai do checkout principal, sincronizar
antes ou rodar o reprocesso lá. Depois: `make publicar-dados` + deploy; conferir `/api/evolucao/pessoas` não vazio.
