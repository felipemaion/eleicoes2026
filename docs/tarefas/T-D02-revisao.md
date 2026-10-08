# T-D02 — correções da revisão (PR #29) — branch `feat/dados-parsers` — PRIORIDADE
1. [ALTA/privacidade] `tse_csv.py:35-41`, `processar.py:268-283`: CSV transcodificado (com CPF/título)
   fica em `raiz_proc/.etl-*` até o fim; SIGKILL deixa CPF em `processed/` (pasta publicável).
   Temporário fora de `raiz_proc` (`tempfile.mkdtemp`, modo 0700) e apagar o `.utf8.csv` ao fim de cada
   membro (`try/finally`). Teste: nenhum arquivo com CPF sob `processed/` em nenhum momento observável.
2. [ALTA] `processar.py:42-47` `hash_pessoa`: exigir CPF com 11 dígitos (DV válido) e título com 12;
   rejeitar dígitos todos iguais. Testes: CPF zeros, CPF com ≥ 12 dígitos.
3. [ALTA] `processar.py:194-212,220` total de controle circular (sentinelas já viraram nulo dos dois
   lados). Esperado calculado do CSV em texto (`infer_schema=False`, cast não estrito), somando ≥ 0 e
   contando sentinelas; logar nulos por sentinela/coluna. Fixture com sentinelas.
4. [ALTA] `processar.py:126-132` `_agregar_locais` não determinístico e pode montar lat/lon que nunca
   existiu: ordenar por `nr_secao` (ou `maintain_order=True`) e anular lat/lon juntas. Teste.
5. [ALTA] `processar.py:272-281` publicação parcial: validar todos os membros em `.tmp` e só então
   publicar (troca de diretório `ano=N.tmp/` → `ano=N/`) + manifesto.
Depois: `make lint test`, reprocessar 2022/2026, commit, seção "Revisão" no handoff, responder
`pronto revisão D02`, e então voltar à T-D03.
