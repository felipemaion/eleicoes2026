# Eleicoes2026 — desempenho do Partido Missão

Dashboard interativo e público que compara, por **município** e **zona eleitoral**, o desempenho
dos candidatos do **Partido Missão (14)** nas eleições gerais de 2026 com o grupo de candidatos do
**MBL em 2022** (quando ainda concorriam por outros partidos): mapa de densidade de votos,
indicadores de desempenho e de gasto de campanha (custo por voto, origem das receitas) e a
evolução entre as duas eleições.

🔗 **https://eleicoes2026.maionesys.com**

## Dados
Somente fontes oficiais: **TSE** (Portal de Dados Abertos), **IBGE** (malhas municipais) e
**BCB** (IPCA). Detalhes em [`docs/fontes-de-dados.md`](docs/fontes-de-dados.md); metodologia em
[`docs/metodologia/`](docs/metodologia/).

## Pilha
FastAPI · DuckDB/Parquet · polars · Vite + TypeScript · D3 v7 · MapLibre GL · PMTiles · H3.
Arquitetura em [`docs/arquitetura.md`](docs/arquitetura.md).

## O que o painel mostra
- **Visão geral**: KPIs do grupo (votos, % dos válidos, penetração, custo por voto) e ranking.
- **Mapa**: penetração por município/zona (coroplético, mesmas quebras entre anos) e densidade de votos.
- **Gastos**: custo por voto (contratado e pago, sem repasses), receita por fonte, % de dinheiro público.
- **Evolução 2022×2026**: MBL 2022 (18 candidaturas, `data/reference/mbl_2022.csv`) → MBL 2026 / Missão 2026,
  mapas lado a lado e de diferença por AMC, swing, retenção e ganho.
- **Candidato**: ficha com gastos completos, links oficiais do TSE e a fonte de cada número.
- Busca global (`/`), filtros dependentes, mapa focado na região do candidato, hover com detalhes. **Como ler este painel**: metodologia em linguagem simples.

Números conferidos contra o TSE: ver [`docs/metodologia/conferencia.md`](docs/metodologia/conferencia.md).

## Atualizar os dados
```bash
make etl ANO=2026 && make etl ANO=2022     # local (Mac): baixa e processa as fontes oficiais
make publicar-dados DIR=data/processed     # rsync para o servidor (rsync oficial: brew install rsync)
```
O deploy do código é automático a cada merge na `main` (`.github/workflows/deploy.yml`).

## Desenvolvimento
```bash
make setup   # dependências e hooks
make test    # testes
make dev     # API + web locais
```
Convenções (TDD, git, agentes) em [`CLAUDE.md`](CLAUDE.md) e [`docs/fluxo-de-trabalho.md`](docs/fluxo-de-trabalho.md).
Plano e decisões: [`docs/plano.md`](docs/plano.md), [`docs/adr/`](docs/adr/), [`docs/registro/`](docs/registro/).

## Licença
Código sob [MIT](LICENSE). Dados públicos do TSE, IBGE e BCB, sujeitos aos termos das fontes.
