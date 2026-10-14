# Handoff dados — T-D10 (finanças de todos os candidatos + fotos)

## Achado principal (exige ação do backend)
O ETL **já processava todos os candidatos** (não há filtro de grupo em `processar.py`/CLI). Os Parquet locais
têm Lula (R$ 87,6 mi), Flávio Bolsonaro (R$ 68,7 mi) etc. O `gastos: null` vem da **API**:
`apps/api/src/api/repositorio/duckdb.py` filtra `nr_turno = 1` nas views `receitas`, `despesas` e em
`_prestacao_da_base` (linhas ~388, 406, 409, 424). O TSE grava a prestação **cumulativa** de quem foi ao
2º turno só com `nr_turno=2` → ficam de fora 16 candidatos em 2026 (2 presidentes + 14 governadores) e 52 em
2022 (4 + 48, p.ex. Lula e Bolsonaro). Verificado: nenhum candidato tem os dois turnos (sem dupla contagem),
logo basta **remover o filtro de turno das contas**. Reproduzido localmente (ficha do Lula → `gastos: None`).
**Pedir ao orquestrador:** tarefa de backend + republicar. Nenhum dado precisa ser reprocessado.

## O que fiz
- Cobertura medida (candidatos com receita / total): 2026 pres 13/14, gov 195/201, sen 313/319, DF 7458/7803,
  DE 10817/11295, DD 413/433; 2022 pres 15/15, DF 10420/10630, DE 16455/16737. Faltantes = vice/suplente/sem contas.
- Testes novos em `packages/etl/tests/test_contas.py`: totais por partido×cargo = arquivo oficial (todos os
  partidos, inclui presidente) e prestação com `ST_TURNO=2` preservada sem duplicar (total de controle).
- `docs/fontes-de-dados.md`: regra do turno 2.

## Tamanho e tempo
Parquet de contas, 2022+2026: receitas 1,8 MB; contratadas 3,2 MB; pagas 2,9 MB (≈ 8 MB, 28 arquivos por UF
por ano). Reprocessar contas 2026 (ZIP de 190 MB): **≈ 4 s**. Sem partição extra necessária.

## Fotos
Presidentes 2026 (Lula, Flávio, Caiado, Zema, Cury etc.) e 2022: todas presentes. Eleitos DF/DE/DD: nenhum
faltante (2026 e 2022). Única ausência 2026 nos cargos 1–8: `GUSTAVO GALASSI` (PSDB, senador MG,
sq 130002553354), provavelmente sem foto no TSE. 2022: 25 sem foto (1 gov, 1 sen, 8 DF, 13 DE, 2 DD).

## Pendência
Conferência com DivulgaCandContas **não feita**: a API é bloqueada (Akamai "Access Denied") fora de navegador.
Conferência interna feita (soma de controle em centavos contra o CSV oficial em cada processamento). Sugestão:
conferir no navegador Lula 2026 (≈ R$ 87,64 mi receitas), Flávio (≈ R$ 68,70 mi) e Lula 2022 (≈ R$ 135,54 mi).

## Como verificar
`uv run pytest packages/etl/tests/test_contas.py` · `make lint test`.
