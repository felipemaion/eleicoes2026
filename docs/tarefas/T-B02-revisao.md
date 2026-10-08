# T-B02 — correções da revisão (PR #32) — branch `feat/backend-endpoints`
1. [DRY, alto] `servicos/adaptador_indicadores.py` inteiro reimplementa `packages/indicadores` (já na main).
   Remover e usar: `desempenho.penetracao/pct_validos/votos_km2/totais_uf/indicadores_municipais`,
   `financeiro.classificar_receitas/resumo_receitas/despesa_campanha/custo_por_voto/custo_por_voto_agregado/
   serie_ipca/fator_ipca/resolver_mes_base/corrigir_ipca`, `evolucao.agregar_amc/evolucao`,
   `grupos.agregar_grupo`. Também `comparativo.py:180-200` (`_kpis` à mão), `municipio.py:111`,
   `contas.py:98-110`. Serviço = orquestra consulta + chama `indicadores`; nenhuma fórmula local.
   Se faltar algo em `indicadores`, liste no handoff (pedido à `analise`), não implemente.
2. [B1] IPCA: `contas.py:13` fixa `MES_BASE_IPCA="2026-09"` → 503. Usar `financeiro.resolver_mes_base`
   (ADR 0007 emenda: último mês disponível); `base_ipca` = mês realmente usado; cachear a série.
3. [B2] Quebras: `mapa.py:85-89` quintis por resposta. Spec §8.2: quebras comuns 2022+2026 sem n baixo.
   A `analise` vai publicar `indicadores.espacial.quebras_comuns(...)` (T-A06); até lá deixe o ponto de
   uso isolado numa função e um teste marcado xfail; `len(valores)<2` não pode devolver `[]` silencioso.
4. [B3] Desempenho: `duckdb.py:46-47,127` `hive_partitioning=false` → ligar hive (poda por `ano=`) ou
   filtrar no `read_parquet`; `municipio.py:88-102` filtrar `cd_mun_ibge` no SQL; cache LRU nos
   serviços por (ano, cargo, uf, grupo) invalidado por `dt_geracao`; `/mapa` nacional sem UF com cache.
5. [B4] Provisórios (receitas/despesas/ipca): validar colunas mínimas na abertura (falha clara), sem `SELECT *`.
