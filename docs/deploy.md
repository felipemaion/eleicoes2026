# Deploy — eleicoes2026.maionesys.com

Recomendação do agente **Oracle** (`~/Projects/OracleServer`, consultado em 2026-10-07).

## Servidor
Oracle Cloud `VM.Standard.A1.Flex` **ARM64**, 2 OCPU, 12 GB RAM, 193 GB disco. Docker + Caddy +
Cloudflare (proxied, SSL Full strict). **CPU é o recurso escasso** (outros 4 serviços em produção).

## Decisões
- **DuckDB + Parquet embutido** — não há Postgres no servidor; o backup só cobre SQLite; Parquet é
  reprodutível a partir do TSE. PostGIS só se surgir consulta espacial dinâmica real.
- **ETL local** + `rsync` dos Parquet para `datasets/` (não `data/`, que entra no backup).
- Container: `cpus: "1.0"` (teto 1.5), `mem_limit: 2g`, DuckDB `SET threads=2`.
- Container **não publica porta**: entra na rede Docker `proxy`; Caddy alcança pelo nome.
- **Caddy serve o bundle Vite e os PMTiles** (Range requests); só `/api` vai ao FastAPI.
- Tiles com **hash no nome** — a Cloudflare reescreve `Cache-Control`.
- Definir caminhos estáticos **antes** do primeiro deploy: montagem nova no Caddy exige recriar o
  container e derruba todos os domínios por segundos.

## O Oracle provisiona
User `eleicoes01`, `/home/eleicoes2026.maionesys.com/{repo,data,secrets}`, deploy key read-only,
`forced-command`, bloco no Caddyfile, DNS Cloudflare, `deploy.sh` com `flock` e gate de health.

## Nós entregamos ao Oracle (fase F3)
- Repo `felipemaion/eleicoes2026` e branch `main`.
- `Dockerfile` que builda em **arm64**; porta interna (8000); `GET /api/health` (gate).
- Lista de variáveis secretas (em `secrets/env`, nunca no repo). O sal do `pessoa_id` não vai ao
  servidor (só o ETL local precisa).
- App só lê dados (`datasets/` montado read-only).
- Lista definitiva de caminhos estáticos (`/`, `/assets/*`, `/tiles/*`).

## Como está em produção (2026-10-08)
- Imagem `ghcr.io/felipemaion/eleicoes2026-api:latest` (arm64, público), build no Actions (`ubuntu-24.04-arm`),
  environment `production` restrito à `main`; `deploy.sh` (forced-command) faz pull + up com gate de health.
- Compose do Oracle: `ELEICOES_DIR_DADOS=/datasets` (:ro), `ELEICOES_DUCKDB_THREADS=2`, `cpus 1.0`, `mem 2g`.
  DuckDB: `memory_limit 1200MB`, `max_temp_directory_size 400MB`, `/tmp/duck`.
- Estáticos por container Caddy próprio (`eleicoes2026-static`) em `public/`: bundle (rsync do Actions, preserva
  `tiles/` e `fotos/`), `tiles/` e `fotos/` (rsync do Mac por `publicar-dados.sh`).
- Chaves (Mac): `eleicoes-deploy` (dispara deploy), `eleicoes-rsync-public` (public/), `eleicoes-rsync-datasets`
  (datasets/), todas com rrsync/forced-command. Exigem o **rsync oficial** (openrsync do macOS falha).
- Incidentes resolvidos: usuário com shell `nologin` (forced-command não rodava); OOM do DuckDB por semi-join
  (T-B11); 503 por semáforo durante o aquecimento (fila por vaga).
