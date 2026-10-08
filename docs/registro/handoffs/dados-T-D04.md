# Handoff dados — T-D04 (municípios, malhas, AMC, zonas, PMTiles)
Branch `feat/dados-municipios` (3 commits: test → feat → fix do teste de CPF). `make lint test` do pacote verde (cobertura etl+contratos 92%).

## Entregue
- `data/processed/municipios.parquet` (contrato `municipios` em `contratos/geo.py`; chave `cd_mun_ibge`): 5.571 linhas com `cd_mun_tse, sg_uf, nm_municipio, area_km2, cd_amc`. **Nome/colunas alinhados ao backend** (`<dir>/municipios.parquet`; ele lê `cd_mun_ibge, cd_amc, area_km2`).
- `data/processed/tiles/municipios.c6dd69863496.pmtiles` (**31,3 MB**, meta < 60) + `tiles/manifesto.json`. Camadas, zoom 3–10: `ufs` (27), `municipios` (5.571; `cd_mun_ibge` int, `nm`), `zonas_2022` (5.851), `zonas_2026` (6.105; `cd_mun_ibge, nr_zona, id`). Conferido com `pmtiles show`.
- Comandos: `etl baixar --ano 2026 --fonte areas_ibge --fonte malha_municipios --fonte malha_ufs`; `etl geo` (~60 s). `uv.lock`/`packages/etl/pyproject.toml`: + shapely, numpy, fastexcel, pyshp (+ types-shapely).

## Decisões
- **Malha = shapefile oficial `BR_Municipios_2025.zip` (237 MB), não a API v3**: a API não tem Boa Esperança do Norte (5101837) e traz Sorriso/Nova Ubiratã com território antigo. Simplificação 0,0005°. Fonte `malha_ibge` (por UF) removida do catálogo.
- **Área**: XLS oficial IBGE 2025 (mesma malha).
- **AMC**: só 1 desmembramento 2022→2026 (único código de 2026 ausente em 2022): Boa Esperança do Norte, de **Sorriso e Nova Ubiratã** (Lei MT 7.264/2000; STF out/2023; DTB 2024). `cd_amc` = menor código do grupo (5101837 para os três). Dados em `etl.municipios.AGREGACOES_AMC` com fonte.
- Voronoi em graus (planar); coordenada repetida fica com a zona de mais eleitores; local fora do município é descartado.

## Pendências / atenção
- **Zonas sem polígono** (nada inventado): 2022 = 251 zonas (locais sem coordenada no TSE: 13.531 de 184.848), 2026 = 1 (`1600055-11`). As zonas vizinhas ocupam o espaço delas. Lista em `etl geo` (saída JSON). Locais sem município (exterior): 416 / 916.
- 2022: locais de Sorriso/Nova Ubiratã dentro do território hoje de Boa Esperança do Norte são descartados (polígonos atuais).
- Sugestão ao orquestrador: incluir `etl geo` no `make etl` (Makefile fora do meu território); `pipeline_geo.py` só tem cobertura por execução real (30%).
- Commit à parte: `test_cpf_nunca_toca_processed` agora usa temp próprio (falhava na suíte completa por `etl-*` de outro processo no /tmp).

## Verificar
`uv run pytest packages/etl packages/contratos -q`; `uv run etl geo`; `pmtiles show data/processed/tiles/municipios.*.pmtiles`.
