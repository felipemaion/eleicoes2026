# Consulta ao Oracle — logs de erro da API (só leitura)
De: orquestrador Eleicoes2026 (tmux `Eleicoes2026:0`). Só consulta: não reinicie nem altere nada.
`GET /api/candidatos/2026/280002540694` dá **500** em produção, mas 200 localmente com o mesmo código e dados.
Suspeita: memória do DuckDB (memory_limit 1200MB) ou temp_directory `/tmp/duck`.
Por favor, cole as últimas ~80 linhas com erro/traceback de `docker logs eleicoes2026-api` (filtre por
"Error|Traceback|Exception|500"), e `docker stats --no-stream eleicoes2026-api`.
Resposta em `/private/tmp/claude-501/-Users-maion-Projects-Eleicoes2026/bef97382-927e-473d-9c0d-362ca1257a5c/scratchpad/oracle-logs.md`; responda só "respondido".
