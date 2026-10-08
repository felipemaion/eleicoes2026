# Recomendação do Oracle — eleicoes2026.maionesys.com

Base: `VM.Standard.A1.Flex` **ARM64**, **2 OCPU**, 12 GB RAM, 193 GB disco, swap 4 GB.
No ar hoje: o proxy Caddy e outros serviços de produção (lista omitida neste registro público). Host usa ~1,1 GB de RAM.
**O recurso escasso aqui é CPU (2 OCPU), não RAM nem disco.** Isso decide quase tudo abaixo.

## 1. Banco: DuckDB + Parquet

**Não existe Postgres nem PostGIS no servidor** — nenhum, em nenhum projeto. A persistência hoje é SQLite e JSON em disco. Subir Postgres faria de vocês o primeiro, com duas consequências:

- `scripts/backup.sh` só sabe tirar snapshot de **SQLite** (`sqlite3 .backup` + `integrity_check`). Um Postgres **não seria coberto** e ninguém receberia erro — simplesmente não haveria backup.
- Mais um daemon competindo pelas 2 OCPU com quatro serviços em produção.

Para carga **somente leitura**, recarregada diariamente e depois raramente, Parquet + DuckDB embutido no container é o encaixe certo: sem daemon, sem backup novo (o Parquet é reprodutível do TSE) e o "índice" é o próprio particionamento dos arquivos (por UF/ano).

Caveat honesto, **confirmem antes de fechar**: a extensão `spatial` do DuckDB em `linux_arm64`. Se a geometria for pré-resolvida no ETL (município/zona já com código IBGE no Parquet), vocês não precisam de GIS no banco e o DuckDB basta com folga. **Só troquem para PostGIS se aparecer necessidade real de consulta espacial dinâmica** — não por precaução.

## 2. ETL: local + rsync dos Parquet

Local, sem hesitar. Descompactar e parsear 3–5 GB de ZIP do TSE satura as duas vCPUs por muitos minutos, e são as mesmas que servem os outros projetos. Subam **só o Parquet** (centenas de MB) por `rsync`. Precedente: outro projeto já sobe arquivos grandes assim.

Bônus: os ZIPs brutos não ocupam disco nem entram em tarball de backup.

## 3. Limites do container

- `cpus: "1.0"` (teto 1.5) e `mem_limit: 2g` — RAM sobra, CPU não.
- **`SET threads=2` no DuckDB.** Sem isso ele usa todos os núcleos que vê, e uma consulta analítica degrada a latência de todos os outros domínios.
- **Parquet não vai em `data/`** se passar de ~1 GB: o `backup.sh` empacota `data/` inteiro e vocês inflariam o backup com arquivo reprodutível. Usem um diretório irmão (ex.: `datasets/`).

## 4. Deploy — padrão da casa, nada novo

Eu provisiono: user de sistema `eleicoes01` (senha travada, grupo `docker`), `/home/eleicoes2026.maionesys.com/{repo,data,secrets}` em `0750`, deploy key read-only, `authorized_keys` com `forced-command` + `no-pty`, bloco no Caddyfile, DNS na Cloudflare (A proxied, SSL Full strict) e `deploy.sh` com `flock` + gate de health.

**O que preciso de vocês:** repo e branch; Dockerfile que builda em **arm64**; porta interna e endpoint de health (o gate do deploy depende dele); lista de envs secretas (entram por `secrets/env`, nunca no repo); e se `data/` precisa de escrita (aí fixo o uid do container).

Regra que não dá para contornar: **o container não publica porta** — entra na rede `proxy` e o Caddy o alcança pelo nome do serviço.

## 5. PMTiles e frontend estático: pelo Caddy

Pelo Caddy, não pelo FastAPI. O `file_server` resolve **Range requests**, que é exatamente como o PMTiles lê um arquivo único, e deixa os workers do uvicorn livres em vez de presos servindo faixas de bytes de centenas de MB. Mesma coisa para o bundle do Vite: só `/api` vai ao backend.

Dois avisos que já nos custaram tempo aqui:

- **Montagem nova no Caddy exige `docker compose up -d`**, que **recria** o container e derruba o proxy por alguns segundos em **todos** os domínios — `reload` e `restart` não bastam. Decidam o que será estático **antes**, para eu fazer isso uma vez só.
- **A Cloudflare reescreve o `Cache-Control` do origin** (medido: origin 3600 → borda 14400, pelo Browser Cache TTL da zona). Não confiem no header do Caddy: versionem o nome do arquivo de tiles (hash no nome) em vez de depender de `immutable`. Já servimos marca velha por 7,7 h por causa disso.

— agente de infra do OracleServer . Consulta respondida sem tocar no servidor.
