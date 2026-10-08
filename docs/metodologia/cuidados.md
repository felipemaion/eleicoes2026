# Cuidados metodológicos

Base: pesquisa do agente de análise (2026-10-07). Fontes no fim.

1. **Legenda não é de candidato.** Votos de legenda vão em série do partido.
2. **Declare o denominador** (válidos, comparecimento ou aptos). Para comparar anos, use aptos.
3. **Rezoneamento**: zonas foram criadas/extintas entre 2022 e 2026 (ex.: TRE-MG Res. 1249/2023).
   Nunca comparar zona pelo número. Comparação temporal por município (IBGE) e H3.
4. **Municípios novos/desmembrados**: crosswalk TSE↔IBGE; agregar ao de origem na série.
5. **Inflação**: deflacionar 2022 por IPCA (SGS 433), mês-base explícito. Os limites de gasto de
   2026 foram mantidos nominalmente iguais aos de 2022 (redução real).
6. **Grupos de tamanhos diferentes**: normalizar por candidato e oferecer o recorte "mesmos
   candidatos nas duas eleições".
7. **Municípios pequenos**: taxas instáveis → suavização bayesiana empírica ou alerta de n baixo.
8. **Contas de 2026 são parciais** até a prestação final — exibir `DT_GERACAO` e aviso.
9. **Voto em candidato inapto é nulo** (CE art. 175 §3º) e o TSE omite o candidato do
   `votacao_candidato_munzona`; quem existir só no `consulta_cand` como INAPTO tem 0 votos no
   painel, não "dado faltante". Ver `conferencia.md`.
10. **Legenda total = `leg_validos + nom_convr_leg_validos`.** Em 2022 o `detalhe_votacao_munzona`
    de SP já embute os convertidos em `qt_votos_leg_validos`; usar a legenda do
    `votacao_partido_munzona` ou `qt_total_votos_leg_validos`, nunca a parcela isolada.
11. **Presidente fica em `BR.parquet`** no processado; somar só as 27 UFs zera o cargo 1.
12. **Custo por voto exclui repasses** a outros candidatos/partidos (§4.2): difere do total de
    despesas do DivulgaCandContas; dizer isso no tooltip.

## Visualização
- Coroplético **só com taxas**; absolutos em símbolos proporcionais (centroide) ou hexbin H3.
- Sequencial (um matiz) para penetração; divergente centrada em 0 para swing, em 1 para LQ (log).
- Paletas seguras para daltônicos (ColorBrewer/viridis).
- 2022 e 2026 **com as mesmas quebras**, lado a lado, mais mapa de diferença.
- Fase 2: bivariado 3×3 (penetração 2022 × 2026; custo/voto × votos), cartograma Dorling.
- Tooltip com absoluto, taxa e eleitorado; rodapé com fonte e `DT_GERACAO`.

## Referências
- Avelino, Biderman & Silva — concentração espacial do voto (BPSR): https://www.scielo.br/j/bpsr/a/xmLcsgG4hX5HFNHJwHr9BZp/?lang=en
- Biblioteca TSE (concentração eleitoral): https://bibliotecadigital.tse.jus.br/items/1319ea6f-094f-4679-a4ac-5b14afd9513e
- Datawrapper — choropleth: https://www.datawrapper.de/blog/choroplethmaps
- TRE-MG Res. 1249/2023 (rezoneamento): https://www.tre-mg.jus.br/legislacao/resolucoes-do-tre/arquivos-2023-resolucoes-tre-mg/tre-mg-resolucao-no-1249-de-31-de-maio-de-2023
