# Provisionamento de eleicoes2026.maionesys.com — feito

**Nenhum domínio caiu.** Consegui evitar a recriação do Caddy por completo, então não precisei de janela — detalhe em "Decisão que mudou o plano", abaixo.

## O que já está no ar (tudo verificado)

| Item | Estado |
| --- | --- |
| User `eleicoes01` | uid 994, gid 985, senha travada (`passwd -S` = `L`), grupo `docker` |
| Diretórios | `/home/eleicoes2026.maionesys.com/{repo,datasets,public,secrets,.ssh}` |
| Checkout | `03db0d8` de `main` — clone HTTPS, **sem deploy key** (repo é público) |
| Artefatos de deploy | `/opt/deploy/eleicoes2026/{deploy.sh,docker-compose.yml,static-Caddyfile}`, dono `root` |
| Chaves | 3 linhas com `forced-command` em `~eleicoes01/.ssh/authorized_keys` (0600) |
| DNS | `A eleicoes2026 → 167.126.3.134`, **proxied**, criado via API |
| Caddy | bloco novo + `reload` — o container segue `Up 3 weeks`, **não foi reiniciado** |
| Container | `eleicoes2026-static` no ar |
| TLS | certificado emitido (DNS-01); provei a cadeia servindo um arquivo temporário por HTTPS e **removi** depois — `public/` está vazio |

Estado atual dos endpoints, os dois esperados: `/` → **404** (sem `index.html` ainda), `/api/health` → **502** (sem imagem ainda).

Permissões com um motivo que vale registrar: o diretório do projeto é `0750`, mas `datasets/` e `public/` são `0755`. O container roda com uid próprio (não `eleicoes01`), e num bind mount o que vale é o modo do **próprio diretório** — em `0750` ele tomaria *permission denied* ao ler os Parquet. São dados públicos, então abrir leitura não custa nada.

## Decisão que mudou o plano (e dispensou a janela)

Servir `/`, `/assets/*` e `/tiles/*` pelo Caddy de borda exigiria **bind mount novo** no compose dele — e montagem nova só entra com `docker compose up -d`, que **recria** o container e derruba todos os domínios por alguns segundos.

Em vez disso, o projeto tem **container estático próprio** (`caddy:2-alpine`, `eleicoes2026-static`) na rede `proxy`, e o Caddy de borda faz `reverse_proxy` para ele. Assim bastou bloco novo + `reload`.

Dois detalhes que tornaram isso possível e que não estavam no runbook:

- O Caddyfile da casa diz "use `restart`, não `reload`", porque `sed`/editores **trocam o inode** e o bind mount de arquivo único não propaga. Mas **`tee -a` preserva o inode**: medi `inode_antes=1050908` e `inode_depois=1050908`. Por isso o `reload` pegou a mudança sem reiniciar nada.
- Validei com `caddy validate` **antes** do reload (`Valid configuration`). Se tivesse erro, o reload recusaria e a config antiga continuaria valendo.

Efeito colateral bom: **nenhum projeto futuro precisa mais mexer no compose do Caddy.**

## Respostas

**1. Build — GHCR, não no servidor.** Buildem arm64 no Actions (`ubuntu-24.04-arm`) e publiquem no GHCR; o `deploy.sh` só faz `pull` + `up -d`. As 2 OCPU são compartilhadas com os outros projetos do servidor — build aqui degrada todos. O compose espera exatamente **`ghcr.io/felipemaion/eleicoes2026-api:latest`**; se o nome for outro, me avisem (o compose é root, vocês não conseguem editar — de propósito).

**2. Estáticos — `rsync` para `/home/eleicoes2026.maionesys.com/public/`.** O container estático monta isso em `/srv` read-only. Mandem `index.html`, `assets/` e `tiles/` juntos; o `file_server` resolve **Range**, que é o que o PMTiles precisa. **Não** empacotem o bundle numa imagem: assim trocar o frontend não exige rebuild nem republicação, e `rsync` só transfere o que mudou.

**3. No GitHub** — environment `production`, com estes nomes exatos:

| Secret | Valor |
| --- | --- |
| `DEPLOY_HOST` | `167.126.3.134` |
| `DEPLOY_USER` | `eleicoes01` |
| `DEPLOY_SSH_KEY` | conteúdo de `~/.ssh/eleicoes-deploy` (privada, no Mac do Felipe) |
| `RSYNC_SSH_KEY` | conteúdo de `~/.ssh/eleicoes-rsync-public` (privada, no Mac) |
| `DEPLOY_KNOWN_HOSTS` | `167.126.3.134 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDh49xdeHaK8SQ+3GQI2N+TM2wKrSTMEsJqVMozMOqLo` |

Gerei as três chaves **no Mac**, não no servidor, para que nenhuma privada passasse por terminal ou transcript. O Felipe copia o conteúdo dos arquivos acima direto para os secrets.

No workflow: `ssh -i <key> eleicoes01@167.126.3.134` dispara o deploy (o argumento é ignorado, o `forced-command` manda), e o `rsync` do bundle usa a outra chave.

**4. Parquet — `rsync` para `datasets/`, com chave separada.** Do Mac:

```
rsync -av --delete ./build/parquet/ -e "ssh -i ~/.ssh/eleicoes-rsync-datasets" eleicoes01@167.126.3.134:
```

O destino vai vazio de propósito: a chave está presa a `rrsync -wo /home/eleicoes2026.maionesys.com/datasets`, então o caminho é imposto pelo servidor e é **somente escrita**, restrito àquele diretório. Chave distinta da do bundle e da de deploy — cada uma revogável sozinha, apagando uma linha do `authorized_keys`.

Sobre o `--delete`: ele apaga no servidor o que não existe mais na origem. Como o `datasets/` é reprodutível do TSE, isso é seguro aqui — mas é a razão de os Parquet **não** ficarem em `data/` (o `backup.sh` empacota `data/` inteiro e infla o backup com arquivo reconstruível).

## O que falta de vocês

1. **Dockerfile arm64** em `apps/api` — hoje não existe nenhum Dockerfile nem compose no repo (procurei em 3 níveis). Usuário não root, expor **8000**.
2. **Workflow do Actions** — build+push no GHCR, depois o `ssh` de deploy e o `rsync` do bundle.
3. **Bundle do Vite + PMTiles** por `rsync` para `public/`.
4. **Parquet** por `rsync` para `datasets/`.

Não precisam de `HEALTHCHECK` no Dockerfile: o compose já define um, batendo em `http://127.0.0.1:8000/api/health` com `urllib` (40s de `start_period`). O gate do `deploy.sh` depende dele — se o health nunca ficar `healthy` em 120s, o deploy falha e mostra os últimos 50 logs.

Quando os 4 itens estiverem prontos, `ssh -i ~/.ssh/eleicoes-deploy eleicoes01@167.126.3.134` sobe tudo. Me chamem se o primeiro deploy falhar.

— agente de infra do OracleServer 
