# Arquitetura

```
TSE / IBGE / BCB (ZIPs e APIs oficiais)
        │  etl/  (papel dados — roda LOCAL; ADR 0002)
        ▼
data/processed/*.parquet  ── contrato: packages/contratos (schemas validados)
        │                        │
        │                        ▼
        │             packages/indicadores (papel analise — funções puras polars→polars)
        ▼                        │
apps/api  FastAPI ◄──────────────┘   DuckDB read-only, threads=2
        │  /api/*  (OpenAPI versionado em docs/api/openapi.json)
        ▼
apps/web  Vite + TS + D3 + MapLibre  ◄── PMTiles e bundle servidos pelo Caddy
```

## Camadas e responsabilidades (SOLID)

| Camada | Responsabilidade única | Depende de |
|---|---|---|
| `etl/fontes/*` | Baixar e parsear **uma** fonte oficial | `contratos` |
| `etl/pipeline` | Orquestrar fontes, validar, escrever Parquet + manifesto | `fontes`, `contratos` |
| `packages/contratos` | Schemas (colunas, tipos, chaves) e enums (UF, cargo, ano) | — |
| `packages/indicadores` | Calcular métricas a partir de DataFrames | `contratos` |
| `apps/api/repositorio` | `Repository` (Protocol) + `DuckDBRepository` | `contratos` |
| `apps/api/servicos` | Casos de uso: grupo, candidato, mapa, gastos, comparativo | `repositorio`, `indicadores` |
| `apps/api/rotas` | HTTP fino: validar entrada, chamar serviço, serializar | `servicos` |
| `apps/web/dados` | Cliente HTTP tipado (tipos gerados do OpenAPI) | OpenAPI |
| `apps/web/componentes` | Mapa, gráficos, filtros — cada um `render(container, dados, opções)` | `dados` |

Inversão de dependência: serviços dependem do `Repository` abstrato; testes de serviço usam
implementação em memória, testes de integração usam DuckDB real sobre fixtures.

## Grupos configuráveis (Open/Closed)

`config/grupos.yaml` define cada grupo comparável:

```yaml
missao_2026: {rotulo: "Partido Missão 2026", ano: 2026, criterio: {partido: 14}}
mbl_2022:    {rotulo: "MBL 2022", ano: 2022, criterio: {lista: data/reference/mbl_2022.csv}}
```

Novo partido = nova entrada. O resolvedor de grupos traduz `criterio` em filtro sobre
`candidatos.parquet` (por partido, por lista de `pessoa_id`/`sq_candidato`).

## Datasets processados (contrato a detalhar em T-D02)

| Parquet | Grão | Chaves |
|---|---|---|
| `candidatos` | candidatura | `ano, sq_candidato` (+ `pessoa_id` hash) |
| `votos_munzona` | candidato × município × zona | `ano, sq_candidato, cd_mun_ibge, nr_zona` |
| `eleitorado_munzona` | município × zona × cargo | aptos, comparecimento, brancos, nulos, válidos |
| `votos_legenda_munzona` | partido × município × zona × cargo | |
| `votos_local` | candidato × local de votação (de seção) | `+ lat, lon, h3` |
| `locais_votacao` | local de votação | `cd_mun_ibge, nr_zona, nr_local, lat, lon, h3, aptos` |
| `receitas`, `despesas` | lançamento agregado por candidato × fonte/tipo | `ano, sq_candidato` |
| `municipios` | município | `cd_mun_ibge, cd_mun_tse, uf, nome, area_km2` |
| `ipca` | mês | índice para deflação |

## Mapas

- Base: MapLibre GL com estilo leve open source (sem API key).
- Polígonos municipais e de zona (Voronoi) em **PMTiles** com hash no nome (cache Cloudflare).
- Valores vêm da API e entram via `feature-state` — geometria é estática, dado é dinâmico.
- Densidade: pontos de local de votação (heatmap/círculos) e hexágonos H3 agregados.
- Escalas e legendas por D3 (uma fonte de verdade para cor).
