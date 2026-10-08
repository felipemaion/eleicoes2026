# Indicadores — especificação

> Documento **do agente `analise`** (tarefa T-A01 completa este rascunho com fórmulas finais e
> vetores de teste). Cada indicador: definição · fórmula · denominador · unidade · recorte ·
> limitações · referência · vetor de teste.

## Desempenho
| Indicador | Fórmula (rascunho) | Observação |
|---|---|---|
| Votos nominais | Σ `qt_votos_nominais` | absoluto — não vai em coroplético |
| % dos válidos | votos / válidos do recorte | proporcional: válidos = nominais + legenda; majoritário: só nominais |
| Penetração | votos / aptos × 1000 | métrica-âncora para 2022×2026 |
| Votos de legenda | Σ legenda do partido | série do partido; nunca repartida entre candidatos |
| Votos/km² | votos / área | só contexto (reproduz densidade populacional) |

## Espaciais
| Indicador | Fórmula (rascunho) | Referência |
|---|---|---|
| Quociente Locacional | (v_ci / V_c) / (v_i / V) | Avelino, Biderman & Silva (BPSR) |
| HHI entre municípios | Σ s_i², s_i = v_ci / V_c | concentração da votação do candidato |
| Dominância (Ames) | v_ci / v_i (fatia do candidato no município) | Ames (1995) |
| Concentração (Ames) | distribuição espacial da votação do candidato | Ames (1995) — tipologia de redutos |
| Moran global / LISA | sobre taxas (penetração, % válidos) | fase 2 |
| Suavização EB | taxa empírica bayesiana para municípios pequenos | sinalizar n baixo |

## Financeiros
| Indicador | Fórmula (rascunho) | Observação |
|---|---|---|
| Custo por voto (contratado) | despesa contratada / votos | |
| Custo por voto (pago) | despesa paga / votos | diferença indica dívida |
| Receita por fonte | Σ receitas por origem | FEFC, FP, PF, próprios, partidos, crowdfunding |
| % público | (FEFC + FP) / receita total | |
| % autofinanciamento | recursos próprios / receita total | |
| Deflação | valor_2022 × IPCA_base / IPCA_2022 | mês-base declarado na UI |

## Evolução 2022 → 2026
| Indicador | Fórmula (rascunho) |
|---|---|
| Swing | %válidos_2026 − %válidos_2022 (p.p.), por município |
| Retenção | votos_2026 / votos_2022, por município |
| Ganho/perda absoluto | votos_2026 − votos_2022 |
| Sobreposição de redutos | correlação dos LQ 2022 × 2026 |
| Mesmos candidatos | recorte por `pessoa_id` presente nos dois grupos |
| Por candidato | totais do grupo / nº de candidatos (grupos de tamanhos diferentes) |
