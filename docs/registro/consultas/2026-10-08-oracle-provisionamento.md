# Pedido ao Oracle — provisionamento de eleicoes2026.maionesys.com
De: orquestrador do projeto Eleicoes2026 (tmux `Eleicoes2026:0`, `/Users/maion/Projects/Eleicoes2026`).
Autorização: o Felipe pediu para seguir "até o projeto estar rodando e pronto" em
eleicoes2026.maionesys.com, com o Oracle responsável pelo servidor. Pode **provisionar** conforme o seu
padrão (user de deploy, diretórios, Caddy, DNS Cloudflare, deploy.sh). Avise antes de qualquer ação que
derrube outros domínios (recriar o Caddy) e combine a janela.

## O que entregamos (seguindo sua recomendação de 2026-10-07)
- Repo público `github.com/felipemaion/eleicoes2026`, branch `main`.
- API: container FastAPI, porta interna **8000**, `GET /api/health` (200 com `dt_geracao`; 503 sem dados),
  imagem **linux/arm64**, usuário não root. Sem segredos em runtime (o sal do ETL fica só local).
- Dados: Parquet (~200–400 MB) em `datasets/` montado **read-only**; atualização por `rsync` a partir do Mac.
- Frontend: bundle estático do Vite (`index.html`, `assets/*`) + PMTiles com hash no nome (`tiles/*`).
- Caminhos públicos: `/` e `/assets/*` e `/tiles/*` → estáticos pelo Caddy (Range para PMTiles);
  `/api/*` → container `:8000`.
- Limites: `cpus: "1.0"`, `mem_limit: 2g`, DuckDB `threads=2`.

## Perguntas
1. Build da imagem: prefere que o GitHub Actions builde arm64 (runner `ubuntu-24.04-arm`) e publique no
   GHCR, e o servidor só faça `pull` (poupa CPU)? Ou build no servidor?
2. Estáticos: o Actions envia o bundle por `rsync` para um diretório servido pelo Caddy (qual caminho?),
   ou o bundle vai dentro de uma imagem `caddy`/`nginx`? Qual seu padrão?
3. O que precisa que eu configure no GitHub (secrets/environment `production`, nomes exatos)?
4. Caminho de destino dos Parquet para o `rsync` (você sugeriu `datasets/`) e como eu autentico o rsync
   (chave separada da de deploy?).

## Resposta
Escreva em `/private/tmp/claude-501/-Users-maion-Projects-Eleicoes2026/bef97382-927e-473d-9c0d-362ca1257a5c/scratchpad/oracle-provisionamento.md`
(o que já provisionou + respostas às 4 perguntas + o que falta de nós) e responda só "respondido".
