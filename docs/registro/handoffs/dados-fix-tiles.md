# Handoff dados — fix/dados-tiles (pedido do frontend, T-W05)

- `tiles/manifesto.json`: `{"camadas": {<nome>: {arquivo, camada, id, limites[oeste,sul,leste,norte]}}}`
  (+ `arquivo`, `sha256`, `bytes`, `zoom`, `gerado_em` no topo). Um único PMTiles com todas as camadas,
  então `arquivo` é o mesmo em cada entrada. `id`: municipios→`cd_mun_ibge`, ufs→`cd_uf`, zonas_AAAA→`id` (`<IBGE>-<zona>`).
- Municípios: `properties` = `cd_mun_ibge`, `nome` (antes `nm`), `cd_amc`. Zonas: acrescentado `nome` ("<Município> — zona N").
- `gerar_pmtiles` agora exige `ids=`; `camada_zonas` aceita `nomes_municipio`.
- Verificar: `uv run pytest packages/etl -q`; regenerar com `etl` geo (tiles precisam ser reconstruídos para refletir o novo formato).
- Pendência: tiles reais ainda não regerados nesta branch; T-D05 (zonas/H3) não foi tocada.
