# Handoff — analise · T-A11 (comparação com candidatos de referência)

Branch `feat/analise-referencias` (a partir de `origin/main` 80d81cd). Commits:
`docs(metodologia): spec…` → `test(indicadores): …` (vermelho: `referencias` inexistente) →
`feat(indicadores): …` (verde) → `docs(metodologia): textos públicos…` → ADR + este handoff.
`make lint test` verde (py 929 passed, 1 skipped; web 36 arquivos / 369 testes). Cobertura de
`referencias.py` e `espacial.py`: 100 %.

## O que foi feito
1. **Spec** `docs/metodologia/indicadores.md` §10 "Comparação com candidatos de referência"
   (Referências viraram §11):
   - §10.0 três blocos (presidente = lista editorial; dep. federal e dep. estadual/distrital por
     UF), o que **não** se compara (presidente × deputado, UF × UF, 2022 × 2026), viés de seleção
     declarado (a régua é o topo) e "não é causalidade".
   - §10.1 regra dos 5 eleitos → vetor `selecao_referencia.json` (11 casos).
   - §10.2 `pct_maiores` (% dos votos nos 10 maiores municípios) e `n_municipios_com_voto`
     → vetor `participacao_maiores.json` (4 casos).
   - §10.3 catálogo do perfil (12 indicadores existentes, cada um com tipo `razao`,
     `diferenca_pp` ou `contexto` e o porquê) e índice relativo à mediana → vetor
     `perfil_relativo.json` (8 casos). Vetores gerados por uma referência independente em Python
     puro (scratchpad `gera_vetores_ref.py`).
2. **Código** (polars→polars, sem I/O):
   - `referencias.PERFIL` — catálogo único (o teste confere contra a tabela da spec, inclusive a ordem).
   - `referencias.selecionar_eleitos(candidatos, n=5, excluir_partidos=(14,), excluir_sq=(), por=("cd_cargo","sg_uf"))`
     → `cd_cargo, sg_uf, posicao, sq_candidato, nr_partido, votos`.
   - `referencias.mediana_referencia(referencia, indicadores, por, minimo=3)` → `por…, indicador, mediana, n`
     (com `minimo=1` dá a mediana dos nossos).
   - `referencias.perfil_relativo(nossos, referencia, indicadores=PERFIL, por, entidade="sq_candidato", minimo=3)`
     → longo: `por…, entidade, indicador, tipo, valor, mediana_referencia, n_referencia, indice`.
   - `espacial.participacao_maiores(tabela, entidade, k=10, unidade="cd_mun_ibge")`.
   - `_colunas`: `DS_SIT_TOT_TURNO`, `NR_PARTIDO` (conferidos com `contratos.CONSULTA_CAND`).
3. **Textos** (`docs/metodologia/publico/textos.json`): indicadores `selecao_referencia`,
   `participacao_maiores`, `perfil_relativo`; tela `referencias`; avisos
   `referencias_nao_causalidade`, `referencias_topo_dos_eleitos`, `referencias_presidenciaveis`,
   `referencias_financas_ausentes` (+ `contas_parciais`); glossário `candidatos_de_referencia`,
   `indice_relativo`, `mediana`; seção nova `referencias` com `blocos.{presidente,
   deputado_federal, deputado_estadual}.{titulo, rotulo, quem}`, `leitura_indice.{razao,
   diferenca_pp, contexto}` e `ui` (sem mediana, sem referência, menos de 5…), placeholders
   locais `{nome} {uf} {n} {indice} {mediana}`. "Como ler": seção "Comparar com candidatos de
   outros partidos".
4. **ADR proposto** `docs/adr/0009-comparacao-com-referencias.md` (status: proposto).

## Decisões
- Situação eleito = `ELEITO | ELEITO POR QP | ELEITO POR MEDIA` (normalizado). Situação nula =
  não totalizado → não entra. Rótulo fora de {eleitos, NAO ELEITO, SUPLENTE, 2º TURNO} → erro.
- Exclusão por **partido** (`nr_partido`), não federação. Em 2022, `excluir_partidos=()` (14 = PTB).
- Mediana exige ≥ 3 valores não nulos dos 5; mediana 0 → razão nula.
- Composições em % usam diferença em p.p. (razão de percentuais engana); `votos`, `pct_validos`,
  `n_municipios_com_voto` e `receita_total` são só contexto (sem índice). `pct_validos` fica sem
  índice porque, no mesmo cargo e UF, a razão dele é igual à da penetração.

## Para o backend (T-B20)
- `nossos` = candidatos do Missão no cargo/UF, uma linha cada, com as colunas do catálogo já
  calculadas pelas funções existentes (`totais_uf`, `concentracao`, `participacao_maiores`,
  `custo_por_voto`, `receita_por_voto`, `resumo_receitas`); `referencia` = mesmas colunas para os 5.
- O critério declarativo do YAML mapeia 1:1 em `selecionar_eleitos` (`n`, `excluir_partido` →
  `excluir_partidos`, `por: uf` → `("cd_cargo","sg_uf")`). Presidente: `por=("cd_cargo",)` com
  recorte Brasil (a função aceita qualquer `por` que contenha `cd_cargo`).
- Os rótulos prontos estão em `textos.json → referencias.blocos.*.rotulo` (o brief da T-B20 cita
  "Renan Santos (MISSÃO)"; o texto público usa "{nome} (Missão)" — alinhar com o frontend).

## Pendências
- `ds_sit_tot_turno` de 2026 não foi conferido com dados reais (não há `data/processed` neste
  checkout); se o ETL trouxer `#NULO#` cru em vez de nulo, a função levanta "situação
  desconhecida" — é o comportamento desejado, mas vale confirmar com o `dados`.
- Conferência TSE dos totais dos 5 por UF depende da T-D10/T-B20 publicadas.
- ADR 0009 aguarda aceite.

## Como verificar
```bash
uv run pytest packages/indicadores -q -k "referencia or participacao or perfil or textos"
make lint test
```
