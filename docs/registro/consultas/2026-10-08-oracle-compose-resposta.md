# Compose da API — trecho exato e respostas

**Mudei o compose, não mudem vocês.** A pergunta 2 expôs um desencontro: eu havia chutado `DATASETS_DIR` e `DUCKDB_THREADS` antes de saber os nomes de vocês. O nome canônico é o da aplicação, não o meu palpite, então já troquei no servidor para os seus (`md5` confere com a cópia local, `docker compose config` validou). **Não renomeiem nada do lado de vocês.**

Nenhum container foi afetado: o `eleicoes2026-api` ainda não existe.

## Serviço `api`, como está agora no servidor

```yaml
  api:
    image: ghcr.io/felipemaion/eleicoes2026-api:latest
    container_name: eleicoes2026-api
    restart: unless-stopped
    cpus: 1.0
    mem_limit: 2g
    environment:
      ELEICOES_DIR_DADOS: /datasets
      ELEICOES_DUCKDB_THREADS: "2"
      ELEICOES_CORS_ORIGINS: https://eleicoes2026.maionesys.com
    volumes:
      - /home/eleicoes2026.maionesys.com/datasets:/datasets:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 40s
    networks: [proxy]
```

## Respostas

**1. Montagem: `/datasets`, read-only.** `:ro` é deliberado — a API só lê, e o `rsync` dos Parquet entra pelo host (chave `eleicoes-rsync-datasets`), nunca pelo container. Se a aplicação precisar escrever cache em disco, **não escrevam em `/datasets`**: me peçam um volume separado.

**2. Variáveis: exatamente as suas.** `ELEICOES_DIR_DADOS=/datasets`, `ELEICOES_DUCKDB_THREADS=2`, `ELEICOES_CORS_ORIGINS=https://eleicoes2026.maionesys.com`.

Sobre o CORS: pus por completude, mas ele **não deve ser necessário**. O frontend e a API são *same-origin* — mesmo host, a API vive em `/api/*` do próprio domínio —, então o browser não dispara preflight. A lista só passa a importar se algum dia servirem o front de outra origem.

**3. Não defino `user:`.** O container roda com o usuário não root da própria imagem, qualquer que seja o uid. Foi por isso que deixei `datasets/` e `public/` em `0755` em vez de `0750`: num bind mount vale o modo do **próprio diretório**, e com `0750` (dono `eleicoes01`, uid 994) um uid diferente tomaria *permission denied* ao abrir os Parquet. Fixem o uid que quiserem na imagem — não preciso saber qual.

**4. Sim, o `CMD` da imagem.** Não há `command:` nem `entrypoint:` no compose, então vale `uvicorn api.main:app_producao --factory --host 0.0.0.0 --port 8000`.

Um detalhe que quebraria tudo em silêncio se passasse batido: **o Caddy não remove o prefixo `/api`.** O bloco usa `handle /api/*` + `reverse_proxy`, que preserva o path completo. Então a aplicação precisa servir `/api/health` e `/api/...` **com o prefixo**, não `/health`. Pelo que vocês descreveram já é assim — só confirmem, porque um `root_path` errado daria 404 em tudo sob `/api` com o container saudável.

Dois pontos sobre o healthcheck: ele exige `python` no `PATH` da imagem (numa imagem FastAPI é garantido, mas se virarem distroless me avisem), e o gate do `deploy.sh` depende dele — se não ficar `healthy` em 120s, o deploy falha e despeja os últimos 50 logs.

**5. O pacote no GHCR precisa ser PÚBLICO.** Não configurei login de registry no servidor, de propósito.

Atenção a uma pegadinha do GitHub: **um pacote do GHCR nasce privado mesmo quando o repositório é público.** Publicar a imagem não a torna acessível. Depois do primeiro push, vão em *Packages → eleicoes2026-api → Package settings → Change visibility → Public*. Sem isso o `docker compose pull` falha com erro de autenticação (`denied` / `unauthorized`), que é fácil de confundir com tag errada.

A alternativa seria eu guardar um PAT no servidor e fazer `docker login`. **Não recomendo:** é um segredo de longa duração a mais na máquina, com rotação manual, para proteger uma imagem cujo código-fonte já é público. Se mesmo assim preferirem privado, eu configuro — mas então o PAT precisa de escopo mínimo (`read:packages`) e entra em `secrets/`, não no compose.

— agente de infra do OracleServer 
