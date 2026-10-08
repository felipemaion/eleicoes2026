# Handoff backend T-B11 (branch `fix/backend-memoria-concorrencia`)

## Causa raiz (diferente do brief)
- `381,4 MiB/381,4 MiB used` é o **`max_temp_directory_size` (400 MB)**, não o `memory_limit` (que já é
  1200 MB no código; nada o sobrepunha). O DuckDB estourou memória, tentou derramar em disco e o teto de temporários acabou.
- **Por que estourava:** `sq_candidato IN (SELECT unnest(?::BIGINT[]))` vira semi-join e o DuckDB agregava a view
  `votos_munzona` inteira (GROUP BY ALL em ~162 MB de Parquet) antes de filtrar. Medido com os dados reais, Renan Santos:
  `votos_territorio` +777 MB de RSS / 0,43 s → com `IN (?, ?, …)` o filtro desce ao scan: **+10 MB / 0,01 s**.
  Ficha completa: pico 1025 MB → 134 MB. Aplicado em `votos_territorio`, `votos_totais`, `votos_h3`, `pontos`,
  `votos_sem_coordenada` (helper `_em_sqs`; só `?` fixos no SQL, valores como parâmetro).

## Feito
1. `RepositorioDuckDB.configuracao()` + log no startup (`uvicorn.error`, INFO) de `memory_limit`, `temp_directory`,
   `threads`, `max_temp_directory_size`. Teste compara com o valor efetivo do DuckDB.
2. Pico de memória reduzido (acima). Limites mantidos (1200MB/400MB).
3. `duckdb.OutOfMemoryException` → `MemoriaInsuficiente` → **503 `memoria_insuficiente`** + `Retry-After: 5` + log.
4. `CacheLRU`: fila com espera de até `ELEICOES_ESPERA_VAGA_S` (padrão 10 s) antes do 503; `baixa_prioridade()` para o
   aquecimento: no máximo 1 vaga e cede na hora (503 interno, ele tenta de novo por até 60 s) se há usuário na fila.
5. **Bug achado pela varredura com dados reais:** `/api/candidatos/2022/{sq}` de VICE-GOVERNADOR dava 500
   (`Cargo('VICE-GOVERNADOR')` em `links.py`). Agora omite o link de votação por cargo quando não há página própria.

## Verificação
- `uv run pytest apps/api` → 199 ok; ruff/mypy limpos; OpenAPI regenerado (sem mudança de contrato além de nada).
- Local, dados reais, `memory_limit=1200MB`: varredura (SP,DF,RJ) 1903 pedidos, **0 × 5xx, 0 × 503**; RSS do processo ~750 MB
  com aquecimento + varredura.
- **Pendente (orquestrador/Oracle):** deploy e varredura/smoke contra produção (item 5 do brief) — não rodei em produção
  (a varredura anterior contra produção ficou sem resposta no monitor). Comando:
  `uv run python apps/api/scripts/varredura.py --base https://eleicoes2026.maionesys.com`.
- Opcional no compose: `ELEICOES_ESPERA_VAGA_S`, `ELEICOES_DUCK_MEMORY_LIMIT`.
