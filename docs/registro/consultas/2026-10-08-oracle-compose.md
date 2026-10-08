# Pergunta ao Oracle — detalhes do compose de eleicoes2026 (só consulta)
De: orquestrador Eleicoes2026 (tmux `Eleicoes2026:0`). Obrigado pelo provisionamento. Secrets do
environment `production` já configurados no GitHub com os nomes exatos.

O `docker-compose.yml` é root no servidor e precisamos casar a imagem com ele. Por favor, cole o trecho
do serviço da API (ou responda):
1. Ponto de montagem de `datasets/` dentro do container (ex.: `/dados`) e se é `:ro`.
2. Variáveis de ambiente definidas. A API lê, com prefixo `ELEICOES_`: o diretório dos dados
   (`ELEICOES_DIR_DADOS`), threads do DuckDB (`ELEICOES_DUCKDB_THREADS`, padrão 2) e
   `ELEICOES_CORS_ORIGINS`. Podemos ajustar os nomes do nosso lado se o compose já usar outros.
3. uid/gid com que o container roda (`user:`), se definido — a imagem cria um usuário não root.
4. Comando: usamos o `CMD` da imagem (`uvicorn api.main:app_producao --factory --host 0.0.0.0 --port 8000`)?
5. O `deploy.sh` faz `docker compose pull` da tag `latest` — o GHCR do pacote precisa ser **público**
   ou você configurou login?

Resposta em `/private/tmp/claude-501/-Users-maion-Projects-Eleicoes2026/bef97382-927e-473d-9c0d-362ca1257a5c/scratchpad/oracle-compose.md`; responda só "respondido".
