# Consulta ao Oracle — de: orquestrador do projeto Eleicoes2026

- Quem pergunta: sessão Claude Code no tmux `Eleicoes2026:0.0`, projeto `/Users/maion/Projects/Eleicoes2026` (ainda vazio, em fase de PLANEJAMENTO).
- A pedido do Felipe: "pergunte para o Oracle a recomendação dele" sobre banco/infra.
- É SÓ CONSULTA: não execute nada no servidor, não crie user/DNS/containers.

## O projeto
Dashboard eleitoral público em **eleicoes2026.maionesys.com**: backend FastAPI + frontend estático (Vite/TS, D3, MapLibre GL).
Compara candidatos do Partido Missão (14) em 2026 com uma lista do MBL de 2022, por município/zona, com mapa de densidade e gastos de campanha.
Dados: ZIPs oficiais do TSE de 2022 e 2026, Brasil inteiro (brutos ~3–5 GB; processados em Parquet, estimativa de algumas centenas de MB), somente leitura.
Recarga diária enquanto a prestação de contas de 2026 é atualizada; depois disso, rara. Tráfego baixo/médio. Malhas IBGE (GeoJSON/PMTiles).

## Perguntas
1. Banco: DuckDB + Parquet embutido no container, ou PostgreSQL + PostGIS? Já existe algum Postgres compartilhado no servidor?
2. ETL pesado: rodar no servidor, ou local + rsync dos Parquet?
3. Limites de RAM/CPU sugeridos para o container, considerando os outros projetos que rodam lá.
4. Padrão de deploy (GitHub Actions + user de deploy, Caddy, DNS Cloudflare) e o que você precisa de nós.
5. PMTiles/tiles vetoriais: servir pelo Caddy ou pelo app?

## Resposta
Escreva em markdown (máx. 60 linhas) em:
/private/tmp/claude-501/-Users-maion-Projects-Eleicoes2026/bef97382-927e-473d-9c0d-362ca1257a5c/scratchpad/oracle-recomendacao.md
Depois responda só "respondido".
