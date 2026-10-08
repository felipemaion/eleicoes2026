# Eleicoes2026 — desempenho do Partido Missão

Dashboard interativo e público que compara, por **município** e **zona eleitoral**, o desempenho
dos candidatos do **Partido Missão (14)** nas eleições gerais de 2026 com o grupo de candidatos do
**MBL em 2022** (quando ainda concorriam por outros partidos): mapa de densidade de votos,
indicadores de desempenho e de gasto de campanha (custo por voto, origem das receitas) e a
evolução entre as duas eleições.

🔗 `https://eleicoes2026.maionesys.com` (em construção)

## Dados
Somente fontes oficiais: **TSE** (Portal de Dados Abertos), **IBGE** (malhas municipais) e
**BCB** (IPCA). Detalhes em [`docs/fontes-de-dados.md`](docs/fontes-de-dados.md); metodologia em
[`docs/metodologia/`](docs/metodologia/).

## Pilha
FastAPI · DuckDB/Parquet · polars · Vite + TypeScript · D3 v7 · MapLibre GL · PMTiles · H3.
Arquitetura em [`docs/arquitetura.md`](docs/arquitetura.md).

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
