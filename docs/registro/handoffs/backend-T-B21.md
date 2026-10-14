# Handoff backend — T-B21 (só quem foi às urnas + funções da T-A11)
Branch `fix/backend-candidaturas-urna` (a partir de origin/main, depois de T-D11 e T-B20).

## O que mudou
- **Repositório** (`duckdb.py`, `memoria.py`, `base.py`, `modelos.py`): `Candidatura.foi_as_urnas` (coluna nova de
  `consulta_cand`, obrigatória em `COLUNAS_MINIMAS`). `candidaturas`, `buscar_candidaturas`, `candidaturas_de_pessoas` e
  `pares_de_pessoas` só devolvem `foi_as_urnas`; `candidatura(ano, sq)` (ficha) devolve qualquer registro.
  Como todo serviço parte dessas listas, contagens (`n_candidaturas`, `n_de/n_para`, KPIs, grupos, mapa, município,
  redes, referências) e médias/medianas (custo por voto, penetração) deixam de incluir registros fora da urna — um ponto só.
- **Contrato**: `CandidatoResumo.foi_as_urnas` (bool) e `situacao` = "Não foi às urnas" quando a fonte não traz situação
  (2026 `#NE`) e o registro não foi à urna. OpenAPI regenerado (`docs/api/openapi.json`).
- **Referências (b)**: `_mediana`/`_indice` removidos; usam `mediana_referencia`, `perfil_relativo`, `participacao_maiores`
  e o catálogo `PERFIL`. Perfil ganhou `pct_maiores`, `receita_por_voto`, `pct_autofinanciamento`.
- **(c) parcial**: `receita_por_voto` (receita total ÷ votos, lib `financeiro.receita_por_voto`) entra no perfil de
  `/api/referencias`; `contas_parciais` (já existente) avisa que as contas são parciais. **Razão de gasto NÃO feita**:
  o pedido final (T-D12) é despesa contratada **e paga** ÷ receita **financeira** + `alerta_declaracao` (<70% / >110%);
  a lib só tem `pct_receita_gasta` = contratada ÷ receita *total* (§4.8), fórmula diferente → **pedir à analise**
  (função nova em `financeiro` + regra do alerta) e depois ligar na API. Retirei `pct_receita_gasta` do perfil para não
  expor a razão enganosa (ela continua só na ficha, já existente, a revisar junto).
- Fixture: `gerar_fixture.py` ganhou `foi_as_urnas` (= tem resultado) e o sq 40 (registro substituído da pessoa B,
  Missão DF/SP, sem situação, 0 votos). Parquets regenerados (mundo base e `fixtures_referencias`).
- Testes: `test_b21_urnas.py` (ficha, listas/busca, contagens, comparativo). Antes da implementação, o sq 40 deixava 16
  testes existentes vermelhos (contagens infladas).

## Decisões / desvios (para a analise/orquestrador)
1. **Mediana com `minimo=1`**: o padrão da lib (≥3 valores, spec §10.3) anularia `custo_voto_pago` (n=1 no vetor da T-B20).
   Mantive os vetores; `n_mediana` informa quantos valores formaram a mediana. Decidir se a API deve aplicar o mínimo 3.
2. **Campos "contexto"** (votos, receita_total…) têm índice nulo na lib; a API já os expunha como razão nosso÷mediana
   (contrato T-B20, vetor `votos`). Mantive via `razao` da lib sobre a mediana da lib.
3. **Campos fora do catálogo** (`hhi`): sem mediana/índice (nulos, `n_mediana` 0). `n_municipios`↔`n_municipios_com_voto`.
4. `situacao` segue nula na fonte; só o rótulo "Não foi às urnas" foi acrescentado.
5. Não rodei a varredura contra produção (dados reais ainda não republicados com `foi_as_urnas`): depois de
   `make publicar-dados` + Deploy, `apps/api/scripts/varredura.py --base https://…`. A API **falha na abertura** se o
   Parquet de `consulta_cand` publicado não tiver `foi_as_urnas` (publicar os dados da T-D11 antes do deploy!).

## Verificar
`uv run pytest apps/api -q`; `uv run ruff check apps/api`; `uv run mypy apps/api/src`; `make openapi` sem diff.
