# Conferência dos números contra o TSE (T-A04)

**Resultado:** o processado (`data/processed`, `dt_geracao` 2026-10-07) e as funções de
`packages/indicadores` **batem exatamente** (diferença 0) com fontes oficiais independentes, em
2026 e em 2022. Em 2022 todas as diferenças brutas se explicam por **uma** regra da totalização
(voto em inapto → nulo), reconciliada voto a voto. **Nenhuma divergência real** encontrada.

Rodado em 2026-10-08 com `packages/indicadores/scripts/conferir.py` (reproduzível; rede só no
script, testes de `indicadores.conferencia` sem rede).

## Método

| Ano | Fonte independente | Por que é independente |
|---|---|---|
| 2026 | JSON de divulgação `resultados.tse.jus.br/oficial/ele2026/{6257,6259}/dados/<uf>/<uf>-c<cargo>-e<eleicao>-u.json` (27 UFs × governador, senador, dep. federal, dep. estadual/distrital + BR presidente) | Outro produto do TSE (o que alimenta o app Resultados), lido sem passar pelo ETL |
| 2022 | `votacao_secao_2022_<UF>.zip` (voto por seção × votável) e `detalhe_votacao_secao_2022.zip`, agregados do zero | O JSON de 2022 saiu do ar (404). A seção é outra granularidade e outro arquivo que o `*_munzona` do ETL; agregamos seção → UF nós mesmos |

- **Nosso lado:** totais UF × cargo do `detalhe_votacao_munzona` (os denominadores do painel);
  votos por candidato via `desempenho.votos_nominais` (a função que o painel usa); legenda por
  partido do `votacao_partido_munzona` (`legenda_validos + nominais_convertidos`, spec §2.4).
- **Comparação:** `indicadores.conferencia.comparar` — `diferenca = nosso − fonte`, tolerância
  0 (contagens inteiras); linha só de um lado vira `so_nosso`/`so_fonte` (falha a conferência).
- **Correspondência de campos (JSON 2026):** `e.te` = aptos, `e.c` = comparecimento, `v.vv` =
  válidos, `v.vnom` = nominais válidos, `v.vl` = legenda, `v.vb` = brancos, `v.tvn` = nulos
  (inclui nulos técnicos); por candidato `vap` = Σ `qt_votos_nominais` **de qualquer destinação**
  (igual aos válidos só quando `dvt = "Válido"`); por partido `tvtl` = legenda total.
- Amostra de UFs para totais/legenda: **SP, RJ, SC, BA, DF**. Missão 2026: **todas as UFs**.
  MBL 2022: as 9 UFs da lista (`data/reference/mbl_2022.csv`).

## Resumo

| bloco | comparações | confere | diverge | só nosso | só fonte | máx. \|dif\| |
|---|---|---|---|---|---|---|
| 2026 totais UF × cargo (27 UFs, 4 cargos, 7 medidas) | 702 | 702 | 0 | 0 | 0 | 0 |
| 2026 totais Brasil — presidente | 6 | 6 | 0 | 0 | 0 | 0 |
| 2026 todos os candidatos (exceto presidente) | 37.678 | 37.678 | 0 | 0 | 0 | 0 |
| 2026 Missão por cargo | 18 | 18 | 0 | 0 | 0 | 0 |
| 2026 Missão por candidato (500 candidaturas) | 1.000 | 1.000 | 0 | 0 | 0 | 0 |
| 2026 legenda por partido × UF × cargo | 1.149 | 1.149 | 0 | 0 | 0 | 0 |
| 2022 omitidos do munzona são todos INAPTOS | 9 | 9 | 0 | 0 | 0 | 0 |
| 2022 totais UF × cargo (amostra) | 80 | 80 | 0 | 0 | 0 | 0 |
| 2022 reconciliação de nulos | 20 | 20 | 0 | 0 | 0 | 0 |
| 2022 todos os candidatos (amostra) | 9.193 | 9.193 | 0 | 0 | 0 | 0 |
| 2022 MBL por candidato | 16 | 16 | 0 | 0 | 0 | 0 |
| 2022 legenda por partido (amostra) | 299 | 299 | 0 | 0 | 0 | 0 |

## Missão 2026 (Brasil, 1º turno) — nosso = JSON TSE

| cargo | candidaturas | votos nominais válidos | votos apurados (todas as destinações) |
|---|---|---|---|
| Presidente | 1 | 2.675.887 | 2.675.887 |
| Governador | 9 | 328.154 | 328.154 |
| Senador | 5 | 684.138 | 684.138 |
| Dep. federal | 319 | 1.150.983 | 1.151.754 |
| Dep. estadual | 153 | 701.978 | 703.446 |
| Dep. distrital | 13 | 12.534 | 12.534 |

A diferença entre "apurados" e "válidos" (771 no federal, 1.468 no estadual) são votos de
candidaturas `Anulado sub judice` — o painel conta só os válidos (spec §2.1). Ex.: SP dep.
federal, partido Missão: `tvtn` 640.258 e legenda 16.133 no JSON = nosso.

## Totais da amostra (nosso = fonte em todas as células)

2026 (JSON): aptos e comparecimento são os mesmos em todos os cargos da UF.

| UF | aptos | comparecimento | dep. fed. nominais válidos | dep. fed. legenda |
|---|---|---|---|---|
| SP | 34.081.699 | 26.394.256 | 22.988.308 | 685.880 |
| RJ | 12.842.517 | 9.845.867 | 8.467.054 | 276.699 |
| BA | 11.304.314 | 9.046.179 | 8.001.270 | 280.546 |
| SC | 5.719.541 | 4.634.550 | 4.109.395 | 122.103 |
| DF | 2.243.988 | 1.817.921 | 1.602.806 | 56.251 |

Brasil, presidente 2026: aptos 158.745.502; comparecimento 125.275.835; válidos 119.300.788.

2022 (seções): SP 34.639.761 aptos / 27.147.847 comparecimento; RJ 12.809.126 / 9.893.658;
BA 11.273.819 / 8.866.459 (8.866.458 nos cargos 6 e 7 — 1 eleitor de diferença entre cargos, igual
na fonte); SC 5.483.962 / 4.471.619; DF 2.193.783 / 1.807.484.

## MBL 2022 — votos por candidato (nosso = soma das seções)

| candidato | UF | votos | | candidato | UF | votos |
|---|---|---|---|---|---|---|
| Kim Kataguiri | SP | 295.460 | | Marcio Labre | RJ | 2.501 |
| Guto Zacarias | SP | 152.481 | | Margareth Prats | SC | 2.650 |
| Renato Battista | SP | 54.551 | | Dr Reiller | GO | 1.297 |
| Cristiano Beraldo | SP | 43.460 | | Moisés Queiroz | RJ | 1.277 |
| Marcos Boettcher | SC | 1.043 | | Coronel Busnello | RJ | 774 |
| Cristiano Caiado | DF | 485 | | Sarg Sousa Maranhão | MA | 427 |
| Prof Dr Major Orlando Furtado | RS | 402 | | Vagner Visoli | SC | 385 |
| Kel Guimarães | SE | 178 | | Frank Lôbo | SC | 63 |

16 de 18 conferidos. Os outros dois não têm voto nominal a conferir: **Helio Secco** foi vice-
governador (sem voto próprio) e **Luziane Escritora** (BA) estava INAPTA — os 23 votos dela nas
seções foram a nulo e o TSE não a lista no `votacao_candidato_munzona` (ver abaixo).

## Diferenças brutas de 2022 e explicação

Comparando seção × munzona sem ajuste, nominais da seção ficam **acima** e nulos **abaixo** do
nosso, sempre na mesma quantidade (ex.: RJ senado 1.573.388; DF dep. federal 24.171). Causa
única, reconciliada voto a voto (bloco "reconciliação de nulos"):

- **Voto em candidato INAPTO no dia da eleição é nulo** (CE art. 175 §3º). A urna registra o voto
  no número (aparece na seção como nominal); a totalização o soma em nulos, e o TSE **omite** o
  candidato do `votacao_candidato_munzona`. Na amostra + UFs do MBL: 235 candidatos omitidos,
  **todos** `INAPTO` no `consulta_cand`; maiores: Daniel Silveira (RJ, senado, 1.566.352), Arruda
  (DF, dep. federal, 17.016), Yara Prado (DF, senado, 9.676).
- **Legenda de partido sem registro válido** idem: PCO no RJ (390 dep. federal, 470 estadual).

Somando esses votos aos nulos da seção, nulos e "nominais + legenda" conferem em todas as 20
combinações UF × cargo.

**Peculiaridade de layout (não é erro de número):** no `detalhe_votacao_munzona` de 2022, SP
traz os nominais convertidos em legenda (CE art. 175 §4º) **dentro** de `qt_votos_leg_validos`
(`qt_votos_nom_convr_leg_validos = 0`: 587 no federal, 6.990 no estadual), enquanto o
`votacao_partido_munzona` os separa. A **legenda total** (`leg + convertidos`) é idêntica nos
dois arquivos e é a que o painel usa (spec §2.4). Por isso a conferência compara "nominais +
legenda" juntos no total da UF e a legenda partido a partido no bloco próprio.

## Custo por voto — 3 candidatos conferidos à mão (2026, SP)

Fonte: DivulgaCandContas (API pública do próprio site, prestação de contas atualizada em 06/10 e
29/09), lida no navegador em 2026-10-08. Nossos valores: processado (T-D03) +
`financeiro.despesa_campanha` + `financeiro.custo_por_voto`. Valores nominais de 2026, contas
**parciais**.

| candidato | contratadas TSE | pagas TSE | repasse a outros (TSE) | nossa contratada própria | nossa paga própria | votos | R$/voto contratado | R$/voto pago |
|---|---|---|---|---|---|---|---|---|
| Kim Kataguiri (DF) | 470.347,01 | 465.347,01 | 64.898,50 | 405.448,51 | 400.448,51 | 520.071 | 0,78 | 0,77 |
| Guto Zacarias (DF) | 209.095,42 | 209.095,42 | 0 | 209.095,42 | 209.095,42 | 41.423 | 5,05 | 5,05 |
| Renato Battista (DE) | 146.567,49 | 141.567,49 | 0 | 146.567,49 | 141.567,49 | 89.489 | 1,64 | 1,58 |

Nosso total antes de excluir repasses = TSE ao centavo nos três, e as receitas também batem
(506.582,55; 224.681,91; 163.068,40). A diferença de Kim é **intencional**: a spec §4.2 exclui
"Doações financeiras a outros candidatos/partidos" do custo da própria campanha, e o
DivulgaCandContas mostra o total com o repasse. O painel deve dizer isso no tooltip do custo por voto.

## Limitações

- 2026 é conferido contra outro canal **da mesma totalização**: pega erro de ETL/agregação
  (dupla contagem, filtro de turno/eleição, trânsito, destinação), não erro do TSE.
- 2022 por seção usa o arquivo de seções gerado pelo TSE em jun/2026 (DF: nov/2022), enquanto o
  munzona é de 2026-10-07; mesmo assim bateu sem resíduo.
- Totais 2022 só na amostra de 5 UFs; candidatos 2022 em 9 UFs. 2º turno não conferido (2026
  ainda não houve; 2022 fora do escopo do painel).
- O presidente fica no `BR.parquet` do processado (layout do TSE), não nas UFs: quem somar só
  as 27 UFs zera o presidente.

## Como reproduzir

```bash
uv run python packages/indicadores/scripts/conferir.py \
    --processed <checkout com dados>/data/processed --saida /tmp/conferencia
```
Na 1ª vez baixa ~2,2 GB para `~/.cache/eleicoes2026/conferencia` (lido em fluxo, sem
descompactar; agregados ficam em cache Parquet). Código de saída 0 = tudo confere; 1 = alguma
linha fora de "confere" (ver `resumo.md` na saída).
