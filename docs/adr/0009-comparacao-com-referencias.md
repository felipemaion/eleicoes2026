# 0009 — Comparação com candidatos de referência: regra dos 5 eleitos e índice à mediana

- **Status:** proposto por analise (T-A11) · 2026-10-14 — aguarda o orquestrador
- **Contexto:** o pedido de 14/10 põe o Missão ao lado de candidatos de outros partidos
  (presidenciáveis; 5 eleitos mais votados por UF em dep. federal e estadual). Os de referência
  têm 10–50× mais votos e são, por construção, o topo dos vencedores; a escolha do conjunto e da
  forma de comparar decide o que o painel afirma, e afeta `config/grupos.yaml` (critério novo de
  ranking, T-B20) e o contrato da API.
- **Decisão:**
  1. **Três blocos que nunca se misturam:** presidente (lista editorial fixa, declarada como tal),
     dep. federal por UF, dep. estadual/distrital por UF. Uma comparação = um cargo × uma UF × um
     ano; a biblioteca falha alto se o recorte não contiver o cargo ou misturar anos.
  2. **Regra de seleção** declarativa: `ds_sit_tot_turno` normalizado ∈ {ELEITO, ELEITO POR QP,
     ELEITO POR MEDIA}, `nr_partido ≠ 14` (por partido, não federação), ordem por votos nominais
     válidos do 1º turno, empate por `sq_candidato`; rótulo de situação desconhecido é erro. Em
     2022 não se exclui o 14 (era o PTB).
  3. **Índice relativo à mediana** dos 5 (n ≥ 3 valores não nulos): razão para taxas, diferença em
     p.p. para composições em %, contexto (sem índice) para totais. Por candidato; o resumo do
     grupo é a mediana dos nossos, nunca a soma do grupo contra indivíduos.
- **Consequências:** `indicadores.referencias` (`PERFIL`, `selecionar_eleitos`,
  `mediana_referencia`, `perfil_relativo`) e `espacial.participacao_maiores`; o backend resolve
  os grupos e não reimplementa fórmula. Textos públicos explicitam "quem × quem", que a régua é
  o topo e que diferença não é causa. Detalhes e vetores: `docs/metodologia/indicadores.md` §10.
