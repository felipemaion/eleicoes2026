# Handoff — analise · T-A01 (spec dos indicadores com vetores)

- **Branch:** `docs/analise-spec-indicadores` (2 commits sobre `origin/main` 455b62d) · 2026-10-07

## O que foi feito
- `docs/metodologia/indicadores.md` reescrito como spec oficial: convenções (null, unidades,
  um cargo por vez, grupo como "candidato coletivo"), 8 decisões pedidas no brief, 18 seções de
  indicador com fórmula/denominador/unidade/recorte/limitações/referência, descartados, mapa de
  colunas × datasets TSE, KPIs da visão geral e escalas de cor.
- `docs/metodologia/vetores/*.json` — 18 vetores (31 casos), incluindo casos-limite: zero votos,
  município sem aptos/sem válidos, candidato em um só município, senado com 2 vagas, AMC com
  desmembramento, v2022 = 0, variância zero, rótulo financeiro desconhecido e mês de IPCA
  faltante (casos `erro`). Calculados por implementação de referência independente (Python puro;
  script fora do repo), conferidos à mão nos casos-chave (HHI 0,58; D 0,13; G 0,0312; Moran 0,4/−1).
- `packages/indicadores/tests/test_vetores.py` — integridade dos vetores (formato, `saida` xor
  `erro`, âncora existente na spec, toda seção "Vetor:" tem arquivo). Commit vermelho antes da spec.
- `docs/adr/0007-metricas-ancora-h3-amc.md` — **proposto** (orquestrador decide).

## Decisões (resumo; detalhe na seção 1 da spec)
H3 canônica res 8, comparação res 7/6 · local sem coordenada fora do H3, alerta > 5 % ·
1º turno padrão, turnos nunca somados, evolução só 1º turno · n baixo = esperados < 20 (NCHS) ·
EB global de Marshall para ranking/LISA, mapa padrão bruto + hachura · IPCA set/2022 → set/2026 ·
Ames = G × D, mediana do cargo×UF entre candidaturas ≥ 10 % QE · evolução ancorada em Δ penetração
por AMC; Senado fora da evolução.

## Pendências / para outros papéis
- **dados:** confirmar caminho de `consulta_vagas_{ANO}` (QE); tabela AMC (ex.: Boa Esperança do
  Norte/MT); listas de valores distintos de `NM_TIPO_DESTINACAO_VOTOS`, `DS_FONTE_RECEITA`,
  `DS_ORIGEM_RECEITA`, `DS_ORIGEM_DESPESA` (2022 e 2026) para fechar mapeamentos; `despesas_pagas`
  não tem `SQ_CANDIDATO` (ligar por `SQ_PRESTADOR_CONTAS`); `CD_ELEICAO` 2022 estadual = 546.
- **analise (eu):** conferir a notação do índice G no PDF de Avelino–Biderman–Silva (2011) —
  SciELO estava 503 hoje; se houver normalização, vetor `concentracao` v2. IPCA de set/2026 sai
  ≈ 09/10: até lá a deflação falha por desenho.
- **backend/frontend:** vetores são reutilizáveis (formato na seção 0 da spec); escalas na 8.2.

## Como verificar
```bash
uv run pytest packages/indicadores -q      # 39 passed
make lint
```
