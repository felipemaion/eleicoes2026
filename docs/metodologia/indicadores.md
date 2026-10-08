# Indicadores — especificação

> Documento **do agente `analise`** — fonte de verdade metodológica do projeto (T-A01,
> 2026-10-07). Cada indicador: definição · fórmula · denominador · unidade · recorte ·
> limitações · referência · **vetor de teste** (`docs/metodologia/vetores/<nome>.json`).
> Implementação: `packages/indicadores` (T-A02, T-A03). Cuidados gerais: `cuidados.md`.
> ADR proposto com as decisões estruturais: `docs/adr/0007-metricas-ancora-h3-amc.md`.

## Sumário
0. [Convenções](#convencoes) · 1. [Decisões](#decisoes) · 2. [Desempenho](#desempenho) ·
3. [Espaciais](#espaciais) · 4. [Financeiros](#financeiros) · 5. [Evolução](#evolucao) ·
6. [Descartados](#descartados) · 7. [Colunas × fontes](#colunas) · 8. [KPIs e cores](#kpis) ·
9. [Redes sociais](#redes-sociais) · 10. [Referências](#referencias)

---

<a id="convencoes"></a>
## 0. Convenções (valem para todos os indicadores)

- **Vetores.** JSON `{indicador, spec, versao, descricao, tolerancia_absoluta, convencoes,
  casos:[{nome, entrada, saida | erro}]}`. Entrada e saída usam nomes de domínio em minúsculas
  (`cd_mun_ibge`, `aptos`, `votos`…), independentes do layout do TSE — a tradução TSE→domínio é
  do ETL. Comparar com `|obtido − esperado| ≤ tolerancia_absoluta`. Caso com `erro` = a função
  **deve levantar** a exceção (falha alto). Os vetores foram calculados por uma implementação de
  referência independente (Python puro), não à mão.
- **Indefinido é `null`.** Denominador zero ou ausente → `null` (nunca `0`, nunca `inf`, nunca
  `NaN`). Em polars: `None`/`null`; no JSON da API: `null`; no mapa: classe "sem dado" (cinza claro).
- **Votos do candidato** = votos nominais **válidos** (ver [Votos nominais](#votos-nominais)).
  Votos de legenda **nunca** são atribuídos a candidato.
- **Um cargo por vez.** Nenhum indicador soma votos de cargos diferentes (o mesmo eleitor vota
  uma vez para cada cargo; somar dupla-contaria). Grupo com candidatos de vários cargos tem uma
  série por cargo. Cargo padrão da UI: **Deputado Federal** (maior número de candidaturas nos
  dois grupos).
- **Recortes.** `municipio` (código IBGE 7 díg.), `zona` (`cd_mun_ibge, nr_zona` — **só dentro
  do ano**), `h3` (células H3, ver [agregação H3](#agregacao-h3)), `uf`, `brasil`, `grupo`
  (`config/grupos.yaml`). Exterior (`SG_UF = ZZ`, só presidente) entra em `brasil`, fica fora de
  mapas.
- **Grupo como unidade.** Indicador de grupo = mesmo indicador calculado sobre a soma dos votos
  dos membros **no mesmo cargo e na mesma UF** (grupo tratado como um "candidato coletivo").
  Grupos multi-UF: um valor por UF; agregado `brasil` = Σvotos/Σaptos.
- **Turno.** Padrão `nr_turno = 1`. Ver [decisão 1.3](#decisoes).
- **Unidades.** Penetração em **‰ dos aptos** (votos por mil eleitores aptos); % válidos em %;
  diferenças de % em **p.p.**; diferenças de penetração em **‰ (pontos por mil)**; dinheiro em
  R$ nominais de 2026 (2022 corrigido, [deflação](#deflacao-ipca)).
- **Proveniência.** Toda saída carrega `ano`, `dt_geracao` da fonte e, nas contas de 2026,
  `tp_prestacao_contas` (parcial/final).

---

<a id="decisoes"></a>
## 1. Decisões metodológicas (pedidas na T-A01)

### 1.1 Resolução H3 (urbano × nacional)
| Uso | Resolução | Área média da célula | Por quê |
|---|---|---|---|
| Armazenamento canônico (`locais_votacao.h3`) | **8** | ≈ 0,74 km² | separa locais dentro de bairros; resoluções menores saem por agregação exata (`cell_to_parent`) |
| Mapa urbano / municipal (zoom ≥ 11) | 8 | ≈ 0,74 km² | densidade intraurbana |
| Mapa estadual / metropolitano (zoom 7–10) | 7 | ≈ 5,2 km² | |
| Mapa nacional (zoom ≤ 6) | 5 | ≈ 253 km² | |
| **Comparação 2022 × 2026** | **7** (urbano) e **6** (≈ 36 km², estadual) | | mudança de endereço de local de votação entre anos tende a ficar dentro da mesma célula res 7; res 8 confundiria mudança de local com mudança de voto |

Nunca se calcula taxa em resolução fina e se faz média para cima: soma-se `votos` e `aptos` das
filhas e recalcula-se a taxa. Comparação temporal em H3 só para células com `n_baixo = false`
nos dois anos.

### 1.2 Agregação de locais de votação
1. `votacao_secao` → local: soma por `(ano, cd_mun, nr_zona, nr_local_votacao)`; aptos do local =
   Σ `QT_APTOS` das seções (de `detalhe_votacao_secao`, mesmo cargo e turno).
2. Candidato na seção vem como `NR_VOTAVEL`; liga a `sq_candidato` por `(ano, sg_uf, cd_cargo,
   nr_candidato)`. `NR_VOTAVEL` de 2 dígitos em cargo proporcional = **legenda** (série do partido).
   95/96/97 = branco/nulo/anulado — fora.
3. Coordenada do local: `NR_LATITUDE/NR_LONGITUDE` de `eleitorado_local_votacao` **do mesmo
   ano** (o local pode mudar de endereço). Coordenada **inválida** = `-1`/nula, fora do retângulo
   do Brasil, ou fora do polígono do município com folga de 2 km → local **sem coordenada**.
4. Local sem coordenada: **fora do H3**, mas **dentro** de município/zona (nunca jogado no
   centróide — criaria um reduto falso). Por município publica-se `pct_votos_sem_coordenada`;
   acima de **5 %** a camada H3 do município ganha alerta de cobertura.
5. Locais diferentes no mesmo prédio (zonas distintas) se juntam naturalmente na mesma célula.
Vetor: [`agregacao_h3`](#agregacao-h3).

### 1.3 2º turno
- Cargos proporcionais (dep. federal/estadual/distrital): não há 2º turno.
- Governador/presidente: todo indicador recebe `turno ∈ {1, 2}`; **padrão 1**. Turnos **nunca se
  somam**; denominadores (aptos, válidos) vêm do mesmo turno (`NR_TURNO` do `detalhe_*`).
- Comparação 2022 × 2026 usa **somente o 1º turno** (no 2º o conjunto de candidatos é outro).
- `DS_SIT_TOT_TURNO = "2º TURNO"` na linha do 1º turno indica que o candidato foi ao 2º.

### 1.4 Critério de "n baixo"
`n_baixo = E < 20`, com `E = aptos × taxa_referência` (número **esperado** de votos se o recorte
votasse como a UF votou no mesmo candidato/grupo). 20 eventos é o limiar do NCHS/CDC para taxas
não confiáveis (erro-padrão relativo ≳ 23 %, ≈ 1/√20). Usar o esperado (e não o observado) evita
marcar como "confiável" um zero que é só ruído e não pune candidato fraco num município grande.
`aptos = 0` → `n_baixo = true`. Vetor: [`n_baixo`](#n-baixo).

### 1.5 Suavização
**Bayes empírico global de Marshall (1991)**, estimador por momentos (o mesmo do GeoDa "EB
rate"). Uso: rankings de municípios, LISA/Moran e a alternância "suavizada" do mapa. O mapa
**padrão mostra a taxa bruta** com hachura em `n_baixo` (o leitor reconhece o número do TSE no
tooltip, que mostra bruta e suavizada). Vetor: [`suavizacao_eb`](#suavizacao-bayesiana-empirica).

### 1.6 Mês-base do IPCA
Valores de 2022 corrigidos de **setembro/2022** (mês central da campanha de 2022: 16/08–02/10)
para **setembro/2026** (mês central da campanha de 2026: 16/08–04/10) — mesma posição relativa no
ciclo. Valores de 2026 ficam nominais. **Emenda (ADR 0007, 2026-10-07):** enquanto o IPCA de
set/2026 (sai ≈ 09/10/2026) não for publicado, a base é o **último mês disponível** na SGS 433
(`financeiro.resolver_mes_base`) e a UI declara "R$ de <mês/ano> (IPCA)"; falha só se a série não
tiver nenhum mês posterior à origem ou tiver buraco no intervalo. Referência: fator out/2022–ago/2026
= **1,198245** (SGS 433, consulta de 2026-10-07; falta set/2026). Vetor:
[`deflacao_ipca`](#deflacao-ipca).

### 1.7 Tipologia de Ames operacionalizada
Ver [tipologia de Ames](#tipologia-de-ames): eixos índice G × dominância D; corte na **mediana**
do cargo × UF entre candidaturas (de **todos** os partidos) com votos ≥ **10 % do quociente
eleitoral** — o mesmo piso da cláusula de desempenho individual (CE art. 108, red. Lei
14.211/2021), ou seja, candidaturas com chance real de cadeira.

### 1.8 Métricas-padrão da tela de evolução
1. **Δ penetração** (‰) por AMC — métrica-âncora; divergente centrada em 0.
2. **Δ penetração por candidato** quando os grupos têm tamanhos diferentes.
3. Recorte **"mesmos candidatos"** (por `pessoa_id`) como alternância.
4. Secundárias (tabela/tooltip): swing em p.p. de válidos, retenção, ganho absoluto,
   sobreposição de redutos (Spearman e Jaccard).
Unidade espacial: **AMC** (município IBGE com desmembramentos agregados) e H3 res 6/7.
**Senado não entra em evolução**: 2022 elegeu 1 vaga (1 voto por eleitor) e 2026 elege 2 (2
votos) — % de válidos e penetração não são comparáveis. Comparação entre cargos diferentes da
mesma pessoa (ex.: dep. federal 2022 → governador 2026) só por penetração, com rótulo explícito.

---

<a id="desempenho"></a>
## 2. Desempenho

<a id="votos-nominais"></a>
### 2.1 Votos nominais
- **Definição:** votos dados ao número do candidato e **válidos** na totalização.
- **Fórmula:** `votos = Σ QT_VOTOS_NOMINAIS_VALIDOS` sobre linhas com
  `NM_TIPO_DESTINACAO_VOTOS = "Válido"`, somando zonas e `ST_VOTO_EM_TRANSITO ∈ {N, S}`.
  Separados: `votos_anulados` (destinação "Anulado"/"Anulado sub judice") e
  `votos_convertidos_legenda` (destinação "Válido (legenda)": candidato indeferido cujos votos
  vão ao partido — CE art. 175 §4º).
- **Unidade:** votos (absoluto). **Recorte:** todos. **Nunca em coroplético** — símbolos
  proporcionais (área ∝ votos) ou hexbin.
- **Limitações:** em 2026 a totalização pode mudar com julgamentos (sub judice) — exibir
  `dt_geracao`. Conferência T-A04: Σ por UF/cargo = total oficial do TSE.
- Vetor: `vetores/votos_nominais.json`

<a id="pct-validos"></a>
### 2.2 % dos votos válidos
- **Fórmula:** `pct_validos = 100 × votos / QT_TOTAL_VOTOS_VALIDOS`, denominador do **mesmo
  cargo, turno e recorte**. Para proporcional, `QT_TOTAL_VOTOS_VALIDOS` = nominais válidos +
  legenda total; para majoritário, legenda é zero — **uma regra só**.
- **Unidade:** %. **Recorte:** município, zona (no ano), UF, Brasil (só presidente). H3 não tem
  "válidos" por local de forma barata — no H3 usa-se penetração.
- **Limitações:** muda com o comparecimento; para comparar anos use penetração. **Senado 2026**:
  2 votos por eleitor; o denominador já soma os dois votos, as % dos candidatos somam 100.
- Vetor: `vetores/pct_validos.json` (inclui município sem válidos → `null`, candidato com zero
  votos, candidato em um só município, senado com 2 vagas).

<a id="penetracao"></a>
### 2.3 Penetração (métrica-âncora)
- **Definição:** votos por mil eleitores aptos.
- **Fórmula:** `penetracao = 1000 × votos / aptos`, `aptos = Σ QT_APTOS` do mesmo cargo e turno
  (zonas e `ST_VOTO_EM_TRANSITO` somados, como o numerador).
- **Unidade:** ‰. **Recorte:** todos (inclusive H3, com aptos dos locais).
- **Por que âncora:** o denominador não depende do comparecimento nem do número de concorrentes,
  e existe para município, zona e local — é a única taxa comparável entre 2022 e 2026.
- **Limitações:** aptos em trânsito (`ST_VOTO_EM_TRANSITO = S`) ficam no município onde votaram;
  conferir em T-A04 que Σ aptos por UF bate com o eleitorado apto oficial (detecta dupla-contagem).
  Município com `aptos = 0` → `null`.
- Vetor: `vetores/penetracao.json`

<a id="votos-de-legenda"></a>
### 2.4 Votos de legenda, votação do partido e quociente
- **Legenda total:** `QT_TOTAL_VOTOS_LEG_VALIDOS = QT_VOTOS_LEGENDA_VALIDOS +
  QT_VOTOS_NOM_CONVR_LEG_VALIDOS` (`votacao_partido_munzona`). Série **do partido**; nunca
  repartida entre candidatos.
- **Votação do partido:** Σ nominais válidos dos seus candidatos + legenda total.
- **Quociente eleitoral** (CE art. 106): `QE = válidos_UF / vagas`, desprezada a fração ≤ 0,5 e
  arredondada para cima se > 0,5. **Votação em QE** = votação do partido / QE (quão perto de
  cadeiras). **Quociente partidário** (CE art. 107) = ⌊votação do partido / QE⌋.
- **Federação:** se o partido estiver em federação, QE/QP são da federação (`NR_FEDERACAO`); a
  série de legenda continua por partido. (Missão: sem federação em 2026 — conferir `NR_FEDERACAO = -1`.)
- **Unidade:** votos; QE em votos; votação em QE adimensional. **Recorte:** UF (QE só existe na
  circunscrição); legenda também por município/zona.
- **Limitações:** distribuição de sobras (art. 109) **fora do escopo** — eleitos vêm de
  `DS_SIT_TOT_TURNO`, não são recalculados.
- Vetor: `vetores/votos_legenda.json`

<a id="votos-por-km2"></a>
### 2.5 Votos por km²
- **Fórmula:** `votos / area_km2` (área territorial IBGE). **Só contexto** (tooltip): reproduz
  densidade populacional e não informa desempenho. Não vira camada; a camada de densidade é o
  hexbin H3 de votos absolutos e a penetração por célula. `area_km2 = 0` → `null`.
- Vetor: `vetores/votos_km2.json`

---

<a id="espaciais"></a>
## 3. Espaciais

Notação (um candidato/grupo *c*, um cargo, uma UF): `v_ci` votos de *c* no município *i*;
`V_c = Σ_i v_ci`; `v_i` válidos do cargo em *i*; `V = Σ_i v_i`; `s_i = v_ci / V_c` (fatia da
votação de *c* que vem de *i*); `x_i = aptos_i / Σ aptos` (fatia do eleitorado).

<a id="quociente-locacional"></a>
### 3.1 Quociente locacional (LQ)
- **Fórmula:** `LQ_ci = (v_ci / V_c) / (v_i / V)` = `%válidos_ci / %válidos_c,UF`.
  `LQ > 1`: *c* é mais forte em *i* do que na UF.
- **Unidade:** razão. **Recorte:** município (e zona no ano). **Escala:** log₂, divergente em 1.
- **Limitações:** instável com `n_baixo` (hachurar); `V_c = 0` ou `v_i = 0` → `null`.
- **Referência:** Silva & Davidian (2013, BPSR) usam o LQ para identificar áreas de concentração.
- Vetor: `vetores/lq.json`

<a id="concentracao"></a>
### 3.2 Concentração: HHI, N efetivo, dominância de Ames, índice G
- **HHI** entre municípios: `HHI_c = Σ_i s_i²` ∈ (0, 1]; 1 = votação toda num município.
- **N efetivo de municípios** (Laakso–Taagepera): `N_ef = 1 / HHI`.
- **Dominância (Ames):** `D_c = Σ_i s_i · (v_ci / v_i)` — fatia média do candidato nos
  municípios, ponderada pela importância de cada município para ele.
- **Índice G (concentração relativa ao eleitorado):** `G_c = Σ_i (s_i − x_i)²`; 0 = votação
  distribuída exatamente como o eleitorado. É o G "bruto" de Ellison–Glaeser adaptado ao voto por
  Avelino, Biderman & Silva (2011). *Pendência:* conferir a notação exata contra o PDF original
  (SciELO indisponível em 2026-10-07) — se o artigo normalizar (p. ex. por `1 − Σx²`), versão 2
  do vetor.
- **Unidade:** adimensionais. **Recorte:** candidato ou grupo × cargo × UF.
- **Limitações:** HHI e G crescem mecanicamente com poucos votos — ler junto com `V_c`; `V_c = 0`
  → todos `null`. Candidato em um só município: `HHI = 1`, `N_ef = 1`.
- Vetor: `vetores/concentracao.json`

<a id="tipologia-de-ames"></a>
### 3.3 Tipologia de Ames
- **Eixos:** concentração = índice G; dominância = D. Ames (1995) media o "agrupamento" por Moran
  I; usamos G porque é determinístico, não depende de matriz de vizinhança e é o padrão da
  literatura brasileira posterior (Avelino et al.).
- **Corte:** mediana de G e de D no **cargo × UF**, calculada sobre a **população de referência**
  = candidaturas de todos os partidos com `votos ≥ 0,10 × QE`. Classificação: `G > med_G` →
  concentrado, senão disperso; `D > med_D` → dominante, senão compartilhado (estrito; empate na
  mediana vai para baixo).
- **Tipos:** concentrado-dominante (reduto clássico), concentrado-compartilhado,
  disperso-dominante, disperso-compartilhado (voto de opinião).
- Candidatos abaixo do piso recebem tipo, mas com `na_populacao_referencia = false` e aviso
  ("votação pequena demais para tipologia confiável").
- **Limitações:** classificação relativa à UF/ano (não absoluta) — compara bem candidatos da mesma
  disputa; entre anos, comparar a posição relativa, não o rótulo.
- Vetor: `vetores/tipologia_ames.json`

<a id="n-baixo"></a>
### 3.4 Sinalização de n baixo
Ver [decisão 1.4](#decisoes). Aplica-se a toda taxa por município, zona e H3. Visual: hachura
diagonal + opacidade reduzida; tooltip "estimativa instável (esperados < 20 votos)".
Vetor: `vetores/n_baixo.json`

<a id="suavizacao-bayesiana-empirica"></a>
### 3.5 Suavização bayesiana empírica (EB)
- **Fórmula (Marshall 1991, global):** com `r_i = v_i / n_i` (n = aptos):
  `b = Σv / Σn`; `s² = Σ n_i (r_i − b)² / Σ n_i`; `a = max(s² − b / n̄, 0)`;
  `w_i = a / (a + b / n_i)`; `θ_i = w_i r_i + (1 − w_i) b`. Se `a = 0`, tudo encolhe para `b`.
- **Unidade:** proporção (×1000 para ‰). **Recorte:** municípios de uma UF (prior por UF, porque
  a força do candidato é estadual); H3 com prior da UF.
- **Limitações:** prior global (não espacial); municípios com `n = 0` ficam fora. Versão
  espacial (prior local) fica para fase 2 se o global sub-suavizar.
- Vetor: `vetores/suavizacao_eb.json`

<a id="moran-global-e-lisa"></a>
### 3.6 Moran global e LISA (fase 2)
- **Fórmulas (Moran 1950; Anselin 1995):** `z_i = y_i − ȳ`;
  `I = (n / S₀) · Σ_i Σ_j w_ij z_i z_j / Σ z_i²`; `I_i = (z_i / m₂) Σ_j w_ij z_j`, `m₂ = Σ z²/n`.
  Quadrante pelo sinal de `z_i` e da defasagem `Σ_j w_ij z_j`.
- **Pesos:** contiguidade **rainha** entre polígonos municipais, padronizada por linha; município
  ilha (sem vizinho) recebe o vizinho mais próximo por centróide (k = 1).
- **Variável:** penetração **EB** (nunca absoluto, nunca taxa bruta).
- **Inferência:** pseudo-p por 999 permutações condicionais, semente fixa (`20261004`);
  significância 0,05 sem correção no mapa, com nota sobre comparações múltiplas (Anselin 1995).
- Vetor (só a estatística determinística): `vetores/moran_lisa.json`

<a id="agregacao-h3"></a>
### 3.7 Agregação em H3
Regras na [decisão 1.2](#decisoes). Saída por célula: `aptos`, `votos`, `penetracao`, `n_baixo`;
por município: `pct_votos_sem_coordenada`, `alerta_cobertura_h3`.
Vetor: `vetores/agregacao_h3.json` (células ilustrativas; a relação pai/filho vem na entrada
para o teste não depender da biblioteca H3).

---

<a id="financeiros"></a>
## 4. Financeiros

Fonte: prestação de contas de candidatos (`receitas_candidatos`, `despesas_contratadas_candidatos`,
`despesas_pagas_candidatos`). 2026 é **parcial** até a prestação final: toda tela mostra
`dt_geracao` e o selo "contas parciais". Usa-se a prestação **mais recente** por prestador
(`TP_PRESTACAO_CONTAS`, `DT_PRESTACAO_CONTAS`).

<a id="receita-por-fonte"></a>
### 4.1 Receita por fonte, % público, % autofinanciamento
- **Classificação** (primeiro a fonte, depois a origem — o FEFC chega ao candidato com origem
  "Recursos de partido político", por isso a fonte manda):

  | Categoria | Regra |
  |---|---|
  | `fefc` | `DS_FONTE_RECEITA` = Fundo Especial (FEFC); ou fonte Outros Recursos com origem "Fundo Especial de Financiamento de Campanha" (2026) |
  | `fundo_partidario` | `DS_FONTE_RECEITA` = Fundo Partidário; ou fonte Outros Recursos com origem "Fundo Partidário" (2026) |
  | `pessoa_fisica` | origem "Recursos de pessoas físicas" ou "Doações pela Internet" |
  | `recursos_proprios` | origem "Recursos próprios" |
  | `financiamento_coletivo` | origem "Recursos de Financiamento Coletivo" |
  | `partido_outros_recursos` | origem "Recursos de partido político" com fonte Outros Recursos |
  | `outros_candidatos` | origem "Recursos de outros candidatos"; ou "Doações para Campanha" (2026) |
  | `outros` | rendimentos de aplicações financeiras, "Comercialização de Bens com OR/FEFC" (2022), origens não identificadas |

  Rótulos comparados normalizados (caixa, acento, espaços). Rótulo fora da tabela → **erro**
  (nada cai em "outros" por omissão). A tabela cobre **100% das combinações reais** de
  fonte × origem × natureza de 2022 e 2026 (47, fixture
  `packages/indicadores/tests/fixtures/rotulos_receita_2022_2026.json`, T-A07). Linhas com
  fonte/origem nulas são sempre de R$ 0,00 (sem movimento): **filtrar antes** de classificar.
  Natureza: "FINANCEIRO" e "ESTIMÁVEL" (rótulos do TSE; "ESTIMADO" aceito como sinônimo).

  **Origens novas de 2026 (códigos 10030201/02/03).** Em todos os 82 lançamentos o doador é outro
  candidato (CNPJ de campanha, CNAE "atividades de organizações políticas", `SQ_CANDIDATO_DOADOR`
  preenchido): é repasse entre candidatos, detalhado pela origem do dinheiro do doador, e chega com
  fonte "Outros Recursos". Quando a origem nomeia um fundo, o dinheiro é **público** e conta em
  `fefc`/`fundo_partidario` — coerente com o repasse de outro candidato que já chega com fonte FEFC
  (fonte manda) e com o objetivo do `pct_publico`. "Doações para Campanha" é dinheiro privado do
  doador → `outros_candidatos`. Magnitude (dados de 07/10/2026): FEFC R$ 159 mil, FP R$ 5,6 mil,
  doações R$ 6,7 mil — < 0,01% do FEFC recebido. Na "Comercialização de Bens com FEFC" (2022) quem
  paga é o comprador; o fundo só custeou o bem → `outros`, não `fefc`.
- **Fórmulas:** `receita_total = Σ VR_RECEITA` (financeira + estimável);
  `receita_financeira` à parte; `pct_publico = 100 × (fefc + fundo_partidario) / receita_total`;
  `pct_autofinanciamento = 100 × recursos_proprios / receita_total`. Total 0 → `null`.
- **Recorte:** candidato, grupo (Σ), cargo, UF. Não é espacial.
- **Limitações:** transferências entre candidatos do mesmo grupo aparecem como receita de um e
  despesa de outro — no agregado do grupo, excluir os **repasses** (pela origem, não pela
  categoria) cujo doador é do grupo ([§4.6](#receitas-grupo)).
- Vetor: `vetores/receitas.json`

<a id="custo-por-voto"></a>
### 4.2 Custo por voto (contratado e pago) e dívida
- **Fórmulas:** `custo_voto_contratado = despesa_contratada / votos`;
  `custo_voto_pago = despesa_paga / votos`; `divida = contratada − paga`. Despesa **exclui**
  transferências a outros candidatos/partidos (não é custo da própria campanha).
  `votos = 0` → `null` (não infinito).
- **Grupo:** `Σ despesa / Σ votos` sobre candidatos com contas e votos > 0 (agregado, não média de
  razões); a distribuição por candidato é mostrada pela **mediana** (cauda pesada).
- **Ligação:** `despesas_pagas` não traz `SQ_CANDIDATO` — liga por `SQ_PRESTADOR_CONTAS`.
- **Unidade:** R$/voto (2022 corrigido a set/2026). **Escala:** log.
- **Limitações:** 2026 parcial; despesa paga < contratada pode ser dívida ou só atraso de
  lançamento.
- Vetor: `vetores/custo_por_voto.json`

<a id="deflacao-ipca"></a>
### 4.3 Correção pelo IPCA
- **Fórmula:** SGS 433 é **variação % mensal**, não índice. `fator = Π_{m = origem+1}^{base}
  (1 + v_m / 100)`; `valor_base = valor × fator`. Mês ausente → erro.
- Origem set/2022, base set/2026 ([decisão 1.6](#decisoes)).
- Vetor: `vetores/deflacao_ipca.json`

<a id="indicadores-de-receita"></a>
### 4.4 Indicadores de receita — conjunto e porquê (T-A08)

A despesa diz quanto a campanha **custou**; a receita diz **de quem ela dependeu**. O conjunto
abaixo responde, nessa ordem: quanto entrou (total, financeiro × estimável, a preços de 2026), de
onde (fonte/origem, % público, % próprio, % pessoa física, concentração), quanto rendeu em votos e
em alcance (por voto, por mil aptos), o que sobrou (saldo, % gasto), como se distribui no grupo
(média × mediana) e como mudou de 2022 para 2026. Nada é inventado: são razões simples sobre
`VR_RECEITA`, o HHI/N efetivo de Laakso–Taagepera aplicado às fontes (mesma lógica da
concentração espacial, §3.2) e a deflação da §4.3.

| Indicador | Fórmula (por candidato; grupo = Σ numerador / Σ denominador) | Seção · vetor |
|---|---|---|
| `receita_total` (nominal e em R$ do mês-base) | `Σ vr_receita`; 2022 × fator IPCA | 4.1 · `receitas` |
| `receita_<categoria>` (fonte/origem) | Σ por categoria (8, tabela 4.1) | 4.1 · `receitas` |
| `pct_publico`, `pct_autofinanciamento` | 4.1 | 4.1 · `receitas` |
| `receita_financeira`, `receita_estimavel`, `pct_estimavel` | natureza FINANCEIRO / ESTIMÁVEL; `100 × estimável / total` | 4.5 · `receitas` |
| `pct_pessoa_fisica` | `100 × (pessoa_fisica + financiamento_coletivo) / total` | 4.5 · `receitas` |
| `hhi_fontes`, `n_efetivo_fontes` | `Σ_c s_c²`, `1 / HHI` sobre as 8 categorias | 4.5 · `receitas` |
| `receita_repasses_candidatos`, `receita_sem_repasses` | repasses de outros candidatos (pela origem); `total − repasses` | 4.6 · `receitas` |
| receita do grupo sem repasses internos | 4.6 | 4.6 · `receitas_grupo` |
| `receita_por_voto`, `receita_por_mil_aptos` | `total / votos`; `1000 × total / aptos` | 4.7 · `receita_por_voto` |
| `saldo_contratado`, `saldo_financeiro`, `pct_receita_gasta` | receita − despesa; `100 × contratada / total` | 4.8 · `saldo_campanha` |
| média, mediana, p25, p75, máximo por candidato | sobre candidatos com contas | 4.9 · `distribuicao_receita` |
| Δ e var. % 2022→2026 | 2022 deflacionado antes da diferença | 4.10 · `comparacao_receitas` |

Valem para todos: **2026 é parcial** (selo + `dt_geracao`; ver §4); a receita é a da prestação
mais recente por prestador; **sem contas ≠ receita zero** (candidato sem nenhuma linha de receita
nem de despesa fica `null` e sai dos agregados com contagem explícita, como no custo por voto);
valores monetários de 2022 sempre em R$ do mês-base (§4.3), com o mês declarado na tela.
**Não é espacial:** o TSE não localiza a receita; nada de receita em mapa por município.

<a id="composicao-receita"></a>
### 4.5 Composição da receita: % pessoa física, estimáveis e concentração das fontes
- **Definições.** `receita_estimavel = Σ vr_receita` das linhas de natureza ESTIMÁVEL (bens e
  serviços doados, avaliados em dinheiro — Res. TSE 23.607/2019); `pct_estimavel = 100 ×
  estimável / total`. `pct_pessoa_fisica = 100 × (pessoa_fisica + financiamento_coletivo) /
  total`: o financiamento coletivo é **modalidade de doação de pessoa física** (Lei 9.504/1997,
  art. 23 §4º IV), só intermediada por plataforma; a categoria continua separada na barra por
  fonte. Com `s_c = receita_c / receita_total` nas 8 categorias da tabela 4.1:
  `hhi_fontes = Σ s_c²` ∈ [1/8, 1]; `n_efetivo_fontes = 1 / hhi_fontes` ∈ [1, 8] — "de quantas
  fontes de igual peso a campanha equivale" (Laakso–Taagepera 1979; Herfindahl–Hirschman).
- **Denominador:** `receita_total` (financeira + estimável). Total 0 → todos `null`.
- **Unidade:** %; HHI adimensional; N efetivo em "fontes".
- **Limitações:** o HHI depende da granularidade das categorias (comparar só com a mesma tabela,
  que cobre 2022 e 2026). `outros_candidatos` mistura dinheiro de várias origens do doador. Valor
  negativo de `vr_receita` (não ocorre em 2022 nem em 2026, conferido em 07/10/2026) **falha**:
  quebraria fatias e HHI.
- Vetor: `vetores/receitas.json` (v3)

<a id="receitas-grupo"></a>
### 4.6 Repasses entre candidatos e receita do grupo sem dupla contagem
- **Repasse de candidato** é reconhecido pela **origem**, não pela categoria: origem "Recursos de
  outros candidatos" (qualquer fonte) e, em 2026, as origens 1003020x que chegam com fonte Outros
  Recursos ("Fundo Especial de Financiamento de Campanha", "Fundo Partidário", "Doações para
  Campanha"; §4.1). Motivo: o FEFC repassado por outro candidato chega com **fonte FEFC** e cai
  na categoria `fefc` — filtrar por `categoria == outros_candidatos` (regra anterior) deixava
  passar o grosso dos repasses (2022: R$ 162 mi de FEFC e R$ 6,7 mi de FP repassados entre
  candidatos, contra R$ 28,8 mi em Outros Recursos; dados de 07/10/2026).
- **Por candidato:** `receita_repasses_candidatos = Σ` das linhas de repasse;
  `receita_sem_repasses = receita_total − receita_repasses_candidatos` (dinheiro que não veio de
  outra campanha). Ambos saem de `resumo_receitas`.
- **Grupo:** `receita_grupo = Σ receitas dos membros − repasses cujo doador
  (`sq_candidato_doador`) é membro`. O repasse interno é receita de um e despesa (repasse) de
  outro; somar dupla-contaria. Saem também `receita_repasses_internos` (o descontado) e
  `receita_repasses_doador_desconhecido` (repasse com doador nulo: **fica** no total e pode ser
  interno — a tela mostra a faixa `[total − desconhecido, total]`). Os demais indicadores do
  grupo (%, HHI) são recalculados sobre o total sem internos.
- **Pendência de dados:** o contrato `receitas_candidatos` agrega as linhas e hoje **não** guarda
  `sq_candidato_doador` (existe no CSV do TSE, §7); a API passa a coluna nula, então todo repasse
  aparece como "doador desconhecido" — visível, não escondido. Pedido ao orquestrador: o `dados`
  incluir `sq_candidato_doador` (identificador de candidatura, não é dado pessoal) na chave de
  agregação das receitas. A coluna ausente faz a função **falhar**.
- Vetor: `vetores/receitas_grupo.json`

<a id="receita-por-voto"></a>
### 4.7 Receita por voto e receita por mil eleitores aptos
- **Fórmulas:** `receita_por_voto = receita_total / votos` (votos nominais válidos; `votos = 0`
  → `null`). `receita_por_mil_aptos = 1000 × receita_total / aptos`, com `aptos` = eleitorado
  apto da **circunscrição** (UF para deputados, senador e governador; Brasil para presidente).
- **Grupo:** `Σ receita / Σ votos` sobre candidatos **com contas e votos > 0** (agregado, não
  média de razões), mais a **mediana** por candidato (cauda pesada) e as contagens de excluídos —
  mesma regra do custo por voto (§4.2). Por mil aptos no grupo: Σ receita dos membros na UF /
  aptos da UF (o eleitorado entra **uma vez**); `brasil` = Σ receita / Σ aptos das UFs com membro.
- **Por que os dois.** Receita por voto mede quanto dinheiro houve por voto conquistado (irmã do
  custo por voto); receita por mil aptos mede o **peso financeiro** da campanha diante do
  eleitorado — comparável entre UFs de tamanhos muito diferentes e entre 2022 e 2026. Identidade:
  `receita_por_mil_aptos = receita_por_voto × penetração (‰)`.
- **Unidade:** R$/voto e R$ por mil aptos (2022 em R$ do mês-base). **Escala:** log.
- **Limitações:** receita ≠ gasto (há sobra e dívida, §4.8); 2026 parcial puxa os dois para
  baixo até a prestação final; é associação, não efeito causal do dinheiro sobre o voto.
- Vetor: `vetores/receita_por_voto.json`

<a id="saldo-campanha"></a>
### 4.8 Saldo e % da receita gasta
- **Fórmulas:** `saldo_contratado = receita_total − despesa_contratada`;
  `saldo_financeiro = receita_financeira − despesa_paga` (aproxima o caixa: estimáveis não passam
  pela conta bancária); `pct_receita_gasta = 100 × despesa_contratada / receita_total`
  (receita 0 → `null`; acima de 100 % = contratou mais do que arrecadou).
- **Despesa aqui inclui os repasses** a outros candidatos/partidos
  (`despesa_campanha(…, incluir_transferencias=True)`): para o saldo, repassar é uso do dinheiro
  recebido; no custo por voto (§4.2) não é. Estimáveis entram nos dois lados do saldo contratado
  (o bem doado é receita e despesa estimável; agregado de 2022: receita R$ 6,64 bi × contratada
  R$ 6,36 bi).
- `despesa_paga` nula com contratada não nula → 0 (como §4.2); sem despesa contratada → `null`.
- **Recorte:** candidato; grupo = Σ. **Unidade:** R$; %.
- **Limitações:** em 2026 parcial, saldo positivo é sobretudo **atraso de lançamento** de
  despesa, não sobra — mostrar só com o selo "contas parciais". Sobra de FEFC é devolvida ao
  Tesouro na prestação final (Res. TSE 23.607/2019).
- Vetor: `vetores/saldo_campanha.json`

<a id="distribuicao-receita"></a>
### 4.9 Receita por candidato no grupo: média, mediana e quartis
- **Fórmulas** sobre os candidatos do grupo **com contas** (receita não nula; 0 entra):
  `media = Σ / n_com_contas`, `mediana`, `p25`, `p75` (interpolação linear, = `numpy` padrão),
  `maximo`; `n_candidatos` conta todos os membros, `n_com_contas` os que entram.
- **Por quê.** Grupos de tamanhos diferentes (Missão 2026 × MBL 2022) só se comparam **por
  candidato** (§5.3). A receita tem cauda muito pesada (poucos concentram o FEFC): a média diz
  "quanto o grupo tinha por candidato", a mediana "quanto tinha o candidato típico" — mostrar os
  dois, nunca só a média.
- **Recorte:** grupo × cargo × ano (um cargo por vez). **Unidade:** R$.
- **Limitações:** 2026 parcial aumenta `n_candidatos − n_com_contas`; ninguém com contas → tudo
  `null` (não 0).
- Vetor: `vetores/distribuicao_receita.json`

<a id="comparacao-receitas"></a>
### 4.10 Comparação de receitas 2022 → 2026
- **Fórmulas:** para cada coluna monetária `c` (receita total, por categoria, por voto, por mil
  aptos, média/mediana por candidato): `c_2022' = c_2022 × fator_IPCA(set/2022 → mês-base)`
  (§4.3) **antes** da diferença; `delta_c = c_2026 − c_2022'`;
  `var_pct_c = 100 × (c_2026 / c_2022' − 1)` (2022 nulo ou 0 → `null`). Colunas percentuais
  (`pct_*`): sem correção, só `delta` em **p.p.** A função corrige a coluna — o chamador não
  passa 2022 já corrigido (evita corrigir duas vezes).
- **Comparabilidade:** mesmo cargo; grupos de tamanhos diferentes comparados **por candidato**
  (§4.9) ou por mil aptos (§4.7), nunca pelo total bruto sozinho; mesma tabela de categorias nos
  dois anos.
- **Limitações:** 2022 é prestação **final**, 2026 é **parcial** até a final — enquanto o selo
  estiver ativo, Δ negativo de receita é esperado e não significa queda. O TSE não publica
  retratos da prestação de 2022 na mesma distância da eleição, então não há comparação "na mesma
  data". O montante do FEFC muda entre ciclos (2022: R$ 4,96 bi), o que mexe no `pct_publico` de
  todos os grupos.
- Vetor: `vetores/comparacao_receitas.json`

---

<a id="evolucao"></a>
## 5. Evolução 2022 → 2026

<a id="evolucao-2022-2026"></a>
### 5.1 Δ penetração, swing, retenção, ganho absoluto
- **Unidade espacial:** AMC = município IBGE; municípios criados/desmembrados entre 2022 e 2026
  são agregados ao(s) de origem (somam-se votos, aptos e válidos **antes** de calcular taxas).
  Ex. conhecido: Boa Esperança do Norte (MT), desmembrado de Sorriso e Nova Ubiratã — os três
  formam uma AMC (tabela a produzir pelo `dados` a partir das alterações territoriais do IBGE).
  Zona **nunca** (ADR 0003).
- **Fórmulas:** `Δpen = pen_2026 − pen_2022` (‰, âncora); `swing = %válidos_2026 − %válidos_2022`
  (p.p.); `retencao = votos_2026 / votos_2022` (`null` se `votos_2022 = 0`);
  `ganho = votos_2026 − votos_2022`.
- **Recorte:** AMC, H3 res 6/7, UF, grupo; sempre mesmo cargo e 1º turno (exceto o recorte
  rotulado "cargos diferentes").
- **Limitações:** swing e retenção sofrem com mudança de comparecimento e eleitorado — por isso a
  âncora é Δpen. Ganho absoluto só em símbolos, nunca em coroplético.
- Vetor: `vetores/evolucao.json`

<a id="sobreposicao-de-redutos"></a>
### 5.2 Sobreposição de redutos
- **Fórmulas:** ρ de Spearman entre `LQ_2022` e `LQ_2026` por AMC (postos médios em empates;
  variância zero → `null`); **reduto** = AMC com `LQ ≥ 2` e `n_baixo = false`; Jaccard =
  |R22 ∩ R26| / |R22 ∪ R26| (`null` se nenhum reduto). Spearman e não Pearson porque o LQ é muito
  assimétrico.
- **Recorte:** candidato (mesma pessoa) ou grupo, mesmo cargo e UF.
- Vetor: `vetores/sobreposicao_redutos.json`

<a id="por-candidato-e-mesmos-candidatos"></a>
### 5.3 Normalização por candidato e recorte "mesmos candidatos"
- **Por candidato:** `indicador_do_grupo / n`, `n` = candidaturas do grupo **no cargo e
  recorte** com `DS_SITUACAO_CANDIDATURA = APTO` na totalização do 1º turno (candidatos com 0
  votos contam; renúncias antes da urna não). `n = 0` → `null`. Na UF, `n` é o número de
  candidaturas da UF (todas podem ser votadas em qualquer município dela).
- **Mesmos candidatos:** interseção de `pessoa_id` entre os grupos de 2022 e 2026; indicadores
  recalculados só com eles. Mostra-se `n` dos dois lados.
- **Limitações:** MBL 2022 tem 18 candidaturas em vários cargos e partidos; por cargo, `n` é
  pequeno — a UI mostra `n` sempre e evita ranking com n < 3.
- Vetor: `vetores/por_candidato.json`

---

<a id="descartados"></a>
## 6. Descartados ou adiados

| Indicador | Decisão | Por quê |
|---|---|---|
| Votos/km² como camada de mapa | descartado (só tooltip) | reproduz densidade populacional |
| Volatilidade de Pedersen | descartado | mede o sistema partidário; o projeto compara grupos, não o sistema |
| Ames com Moran I no eixo de concentração | adiado (fase 2, junto com LISA) | depende de vizinhança e permutação; G cobre o MVP |
| EB espacial (prior local) | adiado | só se o EB global sub-suavizar |
| Distribuição de sobras / simulação de cadeiras | fora do escopo | eleitos vêm do TSE |
| Comparação de zona por número entre anos | proibido | rezoneamento (ADR 0003) |

---

<a id="colunas"></a>
## 7. Colunas necessárias × fontes do TSE (para o `dados`)

Cabeçalhos conferidos em 2026-10-07 nos arquivos de 2022 e 2026 (iguais nos dois anos para
votação e detalhe). Chaves comuns a todas as linhas de votação: `ANO_ELEICAO, NR_TURNO,
CD_ELEICAO, SG_UF, CD_MUNICIPIO (TSE → IBGE), NR_ZONA, CD_CARGO, ST_VOTO_EM_TRANSITO, DT_GERACAO`.

| Indicador | Dataset TSE | Colunas |
|---|---|---|
| Votos nominais, eleitos | `votacao_candidato_munzona` | `SQ_CANDIDATO, NR_CANDIDATO, NR_PARTIDO, NR_FEDERACAO, QT_VOTOS_NOMINAIS, NM_TIPO_DESTINACAO_VOTOS, QT_VOTOS_NOMINAIS_VALIDOS, DS_SITUACAO_CANDIDATURA, DS_SIT_TOT_TURNO` |
| % válidos, QE | `detalhe_votacao_munzona` | `QT_TOTAL_VOTOS_VALIDOS, QT_VOTOS_NOMINAIS_VALIDOS, QT_TOTAL_VOTOS_LEG_VALIDOS` |
| Penetração, n baixo, G, EB | `detalhe_votacao_munzona` | `QT_APTOS` (+ `QT_COMPARECIMENTO, QT_ABSTENCOES, QT_VOTOS_BRANCOS, QT_TOTAL_VOTOS_NULOS` para contexto) |
| Legenda, votação do partido | `votacao_partido_munzona` | `NR_PARTIDO, NR_FEDERACAO, QT_VOTOS_LEGENDA_VALIDOS, QT_VOTOS_NOM_CONVR_LEG_VALIDOS, QT_TOTAL_VOTOS_LEG_VALIDOS` |
| Quociente eleitoral | `consulta_vagas_{ANO}` (**novo dataset — confirmar caminho**) | `SG_UF, CD_CARGO, QT_VAGAS` |
| H3, densidade | `votacao_secao_{ANO}_{UF}` | `NR_SECAO, NR_LOCAL_VOTACAO, NR_VOTAVEL, QT_VOTOS` |
| H3 (aptos) | `detalhe_votacao_secao` | `NR_SECAO, QT_APTOS` |
| H3 (coordenadas) | `eleitorado_local_votacao` | `NR_ZONA, NR_LOCAL_VOTACAO, CD_MUNICIPIO, NR_LATITUDE, NR_LONGITUDE` |
| Receitas | `receitas_candidatos_{ANO}_{UF}` | `SQ_CANDIDATO, SQ_PRESTADOR_CONTAS, TP_PRESTACAO_CONTAS, DT_PRESTACAO_CONTAS, DS_FONTE_RECEITA, DS_ORIGEM_RECEITA, DS_NATUREZA_RECEITA, SQ_CANDIDATO_DOADOR` (**manter na agregação**, §4.6) `VR_RECEITA, DT_RECEITA` |
| Despesa contratada | `despesas_contratadas_candidatos_{ANO}_{UF}` | `SQ_CANDIDATO, SQ_PRESTADOR_CONTAS, DS_ORIGEM_DESPESA, SQ_CANDIDATO_FORNECEDOR, VR_DESPESA_CONTRATADA, DT_DESPESA` |
| Despesa paga | `despesas_pagas_candidatos_{ANO}_{UF}` | `SQ_PRESTADOR_CONTAS` (sem `SQ_CANDIDATO`!), `DS_FONTE_DESPESA, DS_ORIGEM_DESPESA, DS_ESPECIE_RECURSO, VR_PAGTO_DESPESA, DT_PAGTO_DESPESA` |
| Mesmos candidatos | `consulta_cand` | CPF → `pessoa_id` (hash, ADR 0004), `SQ_CANDIDATO` |
| AMC / crosswalk | `municipio_tse_ibge` + IBGE alterações territoriais | `CD_MUNICIPIO_TSE ↔ CD_MUNICIPIO_IBGE`, origem dos desmembrados |
| Votos/km² | IBGE área territorial | `cd_mun_ibge, area_km2` |
| Deflação | BCB SGS 433 | `data, valor` (variação % mensal) |

Observações para o ETL: (a) `CD_ELEICAO` de 2022 nos arquivos estaduais é **546** (544 é o
federal/presidente); 2026 = 6257/6259. (b) Tipologia de Ames precisa de G e D de **todos** os
candidatos do cargo×UF, não só dos grupos. (c) `NM_TIPO_DESTINACAO_VOTOS`, `DS_FONTE_RECEITA`,
`DS_ORIGEM_RECEITA`, `DS_ORIGEM_DESPESA`: publicar a lista de valores distintos por ano para
fechar os mapeamentos.

---

<a id="kpis"></a>
## 8. KPIs da visão geral e escalas de cor

### 8.1 KPIs (Partido Missão 2026; seletor de cargo — padrão Dep. Federal — e de UF)
1. **Votação do partido** (nominais + legenda) com a quebra nominais/legenda.
2. **Penetração** (‰ dos aptos) — com o valor do MBL 2022 no mesmo cargo ao lado.
3. **% dos válidos**.
4. **Eleitos / candidaturas aptas** e **votação em QE** por UF.
5. **Custo por voto contratado** (agregado do grupo) — selo "contas parciais" + `dt_geracao`.
6. **% recursos públicos** (FEFC + FP).
7. **Δ penetração por candidato** vs MBL 2022 (mesmo cargo), com alternância "mesmos candidatos".

### 8.2 Escalas de cor
| Indicador | Tipo | Paleta (daltônico-segura) | Quebras |
|---|---|---|---|
| Penetração, % válidos | sequencial | viridis (ou ColorBrewer YlGnBu) | 5 quantis do **conjunto 2022+2026** (excluindo `n_baixo`), arredondados; **as mesmas nos dois anos** ([§8.3](#quebras-comuns)) |
| LQ | divergente, log₂, centro 1 | ColorBrewer PuOr | ¼, ½, 0,8, 1,25, 2, 4 |
| Δ penetração, swing | divergente, centro 0 | ColorBrewer BrBG (verde = ganho) | simétricas: ±(máx \|Δ\| arredondado) / 3, 5 ou 7 classes |
| Retenção | divergente, log, centro 1 | BrBG | ¼, ½, 0,8, 1,25, 2, 4 |
| Votos absolutos, ganho absoluto | símbolo proporcional (área ∝ valor) ou hexbin com escala sqrt | um matiz | — |
| Custo por voto | escala log em gráfico (não mapa) | um matiz (Oranges) | — |
| LISA | categórica | convenção GeoDa: alto-alto vermelho, baixo-baixo azul, alto-baixo rosa, baixo-alto azul-claro, não sig. cinza | — |
| Tipologia de Ames | categórica (4) | Okabe–Ito | — |
| `n_baixo` | sobreposição | hachura diagonal + opacidade 50 % | — |
| Sem dado (`null`) | — | cinza claro neutro, distinto de qualquer classe | — |

Bivariado 3×3 (penetração 2022 × 2026) e Dorling: fase 2 (`cuidados.md`).

<a id="quebras-comuns"></a>
### 8.3 Quebras comuns 2022 + 2026 (escalas sequenciais)
- **Para quê:** a mesma cor significa o mesmo valor nos dois mapas (penetração, % válidos). Uma
  chamada por indicador × cargo × recorte (UF ou Brasil) × unidade espacial; o backend passa os
  valores dos dois anos e usa as mesmas quebras nas duas respostas (T-B02: `/mapa`, `/comparativo`).
- **Entrada:** `valores_por_ano = {ano: tabela}`, cada tabela com `valor` (a taxa) e `n_baixo`;
  `k` classes (padrão **5**); `excluir_n_baixo` (padrão **sim**).
- **Conjunto de referência P:** valores **não nulos** de todos os anos, sem as unidades com
  `n_baixo = true` (se `excluir_n_baixo`). Cada unidade-ano pesa 1 (sem ponderar por aptos: a
  escala classifica áreas, não eleitores). `null` é "sem dado" e não entra.
- **Quantis:** `q_j = quantil(P, j/k)`, `j = 1..k−1`, interpolação **linear** (Hyndman–Fan tipo 7:
  posição `h = (|P| − 1)·p`, `q = P₍⌊h⌋₎ + (h − ⌊h⌋)(P₍⌊h⌋+1₎ − P₍⌊h⌋₎)`, P ordenado a partir de 0;
  padrão de numpy, polars e R).
- **Arredondamento:** cada `q_j` a **2 algarismos significativos** (meio para cima, em decimal);
  se o arredondamento fundir dois quantis brutos **distintos**, sobe-se para 3, 4… até 6
  algarismos (todos os limiares com a mesma precisão).
- **Limpeza:** remove-se limiar repetido (empates nos dados, p. ex. muitos zeros) e limiar fora de
  `(min P, max P]` (deixaria classe vazia). Resultado: lista **estritamente crescente** de até
  `k − 1` limiares; com empates, menos classes — a legenda usa `len(limiares) + 1` classes.
- **Classes:** `[b_j, b_{j+1})`, fechadas à esquerda — `valor < b_1` → classe 0, `valor ≥ b_{k−1}`
  → última (convenção de `d3.scaleThreshold`). Unidades `n_baixo` são classificadas com as mesmas
  quebras e hachuradas.
- **Falha alto:** `k < 2`; nenhum ano; coluna ausente; `n_baixo` nulo; valor não finito (NaN/inf
  — indefinido deve vir como `null`); `|P| < 2k` ("poucos valores para k classes"); nenhum
  limiar restante (sem variação).
- **Limitações:** quantis do conjunto pooled — se um ano tiver valores muito maiores, ele ocupa as
  classes de cima (é o efeito desejado: mostrar a mudança). Ano com muito mais unidades pesa mais.
- Vetor: `vetores/quebras_comuns.json`

---

<a id="notas-implementacao"></a>
## 8-A. Notas de implementação (T-A02, `packages/indicadores`)
Escolhas que a spec deixava em aberto, fixadas no código e cobertas por teste:
- **Tabela completa.** `desempenho.montar_tabela` faz o produto entidade × unidade com `votos = 0`
  onde o TSE não traz linha (LQ, G e EB precisam de todas as unidades da UF). Falha alto em linha
  duplicada, voto em unidade sem eleitorado e `votos > validos`.
- **Taxa de referência do n baixo** = penetração (proporção) da entidade na UF; esperado nulo conta
  como n baixo. No H3, a referência usa **todos** os locais recebidos, inclusive sem coordenada.
- **Tipologia** sem nenhuma candidatura na população de referência → medianas e tipos `null`.
- **EB:** com `a = 0` e `b = 0` (nenhum voto) o peso é 0 e tudo encolhe para 0.
- **LISA:** quadrante "alto" se `> 0` (zero conta como "baixo"); pseudo-p `(M+1)/(P+1)` na cauda do
  sinal observado — global por permutação total, local por permutação condicional; ilha (sem
  vizinho) **falha**: o chamador atribui o k = 1 antes.
- **Spearman da sobreposição** usa todas as AMCs com LQ definido nos dois anos (o `n_baixo` só
  restringe quem é reduto).
- **Rótulos do TSE** (fonte/origem/natureza de receita, origem de despesa) são comparados
  normalizados (maiúsculas, sem acento). Tabelas fechadas em `financeiro.py`; rótulo novo falha.
  Repasse excluído da despesa: só "Doações financeiras a outros candidatos/partidos" até o `dados`
  publicar os valores distintos de `DS_ORIGEM_DESPESA` (pendência).
- **Grupos:** `grupos.agregar_grupo` recusa cargos ou turnos misturados; `receitas_grupo` exclui
  os repasses (reconhecidos pela origem, §4.6) cujo doador é membro do grupo.
- **Revisão (T-A06):** `votos_nominais` recusa `nr_turno`/`cd_cargo` com mais de um valor (salvo
  se a coluna estiver nas `chaves`). Custo por voto: `despesa_paga` nula com contratada não nula
  = **0** (nenhuma linha em `despesas_pagas` = nada pago); sem contas, segue nulo.
  `evolucao.evolucao` exige `cd_cargo` e recusa o Senado (§1.8); AMC presente num ano só deixa
  todas as diferenças nulas (ausência ≠ zero). Escalas sequenciais: `espacial.quebras_comuns`
  ([§8.3](#quebras-comuns)).

<a id="redes-sociais"></a>
## 9. Redes sociais (Instagram) — T-A10

Fonte e limites da coleta: [ADR 0008](../adr/0008-redes-sociais-instagram.md) (perfis declarados
ao TSE; métricas da API oficial da Meta, *Business Discovery*). Implementação: `indicadores.redes`.
Entradas = tabelas do `dados` (T-D08): `redes_perfis` (um registro por coleta: `sq_candidato,
username, status, followers_count, follows_count, media_count, coletado_em`) e `redes_posts`
(`username, media_id, timestamp` UTC, `media_type, media_product_type, like_count` — nulo se
oculto —, `comments_count, coletado_em`).

<a id="redes-decisoes"></a>
### 9.0 Decisões comuns
- **Fuso.** O `timestamp` da API é UTC; a janela usa a **data no horário de Brasília (UTC−3)**
  — sem horário de verão desde o Decreto 9.772/2019. Um post às 23h30 de 04/10 (02h30 UTC de
  05/10) é **campanha**, não pós-eleição.
- **Janelas** (datas inclusivas, em Brasília):

  | janela | de | até | dias |
  |---|---|---|---|
  | `pre_campanha` | 01/01/2026 | 15/08/2026 | 227 |
  | `campanha` | 16/08/2026 (propaganda permitida, Lei 9.504/1997 art. 36) | 04/10/2026 (1º turno, CF art. 77) | 50 |
  | `pos_eleicao` | 05/10/2026 00:00 | última coleta da conta | fracionário |
  | `total` | 01/01/2026 | última coleta da conta | fracionário |

  Antes de 01/01/2026 fica fora (a coleta pagina só até essa data). Para quem disputa o 2º turno
  (25/10/2026), `pos_eleicao` inclui a campanha do 2º turno — a tela avisa nesses cargos.
- **Taxa, não total.** As janelas têm durações muito diferentes (227 × 50 dias): compara-se
  `por_semana = 7 × n / dias`. Janela com **menos de 7 dias** → taxa `null` (o `n` continua): três
  dias de pós-eleição não estimam um ritmo semanal (nunca extrapolar).
- **Post repetido** em várias coletas (mesmo `media_id`): vale o da coleta **mais recente**
  (curtidas acumuladas). **Vídeo** = `media_type = VIDEO` (inclui reels,
  `media_product_type = REELS`); carrossel conta como post, não como vídeo (a API não diz o tipo
  dos itens internos sem outra chamada por post).
- **Conta com dados** = `followers_count` não nulo no último snapshot. Conta pessoal ou
  inexistente (`status` ≠ `ok`) não tem métrica: aparece **só com o link** e sai de médias e
  correlações — sempre **contada** (`n_excluidos`, `tem_dados = false`). Candidato sem
  Instagram declarado ao TSE → `status = sem_rede`.
- **Conta principal.** Candidato com mais de uma conta com dados: vale a de **mais seguidores**
  no último snapshot (empate: `username` em ordem alfabética). Somar contas dupla-contaria o
  público comum; as demais aparecem só como link.
- **Seguidores = último snapshot.** A API não tem histórico de seguidores (ADR 0008): o
  denominador do engajamento de um post de março é o público de outubro. Por isso o engajamento
  padrão da tela é o da **campanha** (perto da coleta), não o do ano.

<a id="ritmo-posts"></a>
### 9.1 Posts e vídeos por janela e ritmo de publicação
- **Fórmulas** por conta × janela: `n_posts`, `n_videos`; `posts_por_semana = 7 × n_posts / dias`;
  `videos_por_semana = 7 × n_videos / dias`; `pct_video = 100 × n_videos / n_posts` (sem post →
  `null`). Conta com dados e sem post na janela → `n = 0` e taxa **0** (zero real, não ausência).
- **Variação de ritmo** (por candidato, §9.3): `variacao_ritmo_pct = 100 × (posts_semana_pos /
  posts_semana_campanha − 1)`; campanha sem post ou pós com < 7 dias → `null`.
- **Unidade:** posts/semana; %. **Recorte:** conta (candidato) × janela.
- **Limitações:** post apagado ou arquivado antes da coleta não aparece (a contagem do
  pré-campanha é um piso); stories não vêm na API (somem em 24 h); `media_count` do perfil conta
  a vida inteira da conta e **não** é usado nas janelas.
- Vetor: `vetores/ritmo_posts.json`

<a id="engajamento"></a>
### 9.2 Engajamento por post
- **Fórmula:** `engajamento = 100 × (curtidas + comentários) / seguidores` por post (% dos
  seguidores); por conta × janela, **média** e **mediana** (a cauda de um post viral puxa a
  média — mostrar as duas) e `n_posts_engajamento`.
- **Fora da conta** (post não entra no denominador): curtidas ou comentários **nulos** (curtidas
  ocultas pelo dono: nulo, não zero); post com **menos de 48 h** na coleta (curtidas ainda
  acumulando); seguidores 0 → `null`.
- **Unidade:** % dos seguidores por post. **Recorte:** conta × janela; resumo do candidato usa a
  janela `campanha`.
- **Limitações:** não há visualizações de vídeos de terceiros na API (reel muito visto e pouco
  curtido parece fraco); a taxa cai mecanicamente com o tamanho da conta (contas pequenas têm
  engajamento proporcional maior), então engajamento × votos mistura efeito de tamanho; curtidas
  de posts impulsionados (anúncio) não entram no `like_count` (documentação da Meta).
- Vetor: `vetores/engajamento.json`

<a id="seguidores-votos"></a>
### 9.3 Seguidores × votos por candidato
- **Fórmulas:** `seguidores_por_mil_votos = 1000 × seguidores / votos` (votos 0 → `null`);
  `votos_por_mil_seguidores = 1000 × votos / seguidores` (seguidores 0 → `null`). `votos` =
  votos nominais válidos do candidato no cargo (§2.1), total da UF (Brasil para presidente).
- **Resumo por candidato** (uma linha por candidatura, inclusive sem conta): `username`,
  `status`, `tem_dados`, `seguidores`, as duas razões, `posts_semana_campanha`,
  `posts_semana_pos`, `variacao_ritmo_pct` (§9.1), `pct_video` (janela `total`),
  `engajamento_mediano` e `engajamento_medio` (janela `campanha`).
- **Por que as duas razões:** "votos por mil seguidores" lê como **conversão** do público em voto
  (> 1000 = teve mais votos do que seguidores); "seguidores por mil votos" lê como **tamanho da
  audiência** diante do resultado. São inversas; a tela mostra a primeira.
- **Unidade:** razão por mil. **Recorte:** candidato (um cargo por vez).
- **Limitações:** seguidores incluem **eleitores de outras UFs, menores, estrangeiros e contas
  falsas** — não é uma fração do eleitorado; a conta pode ser anterior à candidatura (público
  construído em outra atividade).
- Vetor: `vetores/seguidores_votos.json`

<a id="serie-seguidores"></a>
### 9.4 Série de seguidores
- **Fórmulas** por conta, snapshots em ordem de `coletado_em`: `delta_abs = seg_t − seg_(t−1)`;
  `delta_pct = 100 × (seg_t / seg_(t−1) − 1)`; `dias` entre as coletas (fracionário). Resumo
  primeiro → último: `n_snapshots`, `delta_abs`, `delta_pct`, `dias`.
- **Só com ≥ 2 snapshots** válidos; com um → variações `null`. Snapshot sem seguidores (conta
  virou pessoal, fora do ar) **sai** da série e a variação seguinte compara com o último válido.
  Nunca interpolar nem extrapolar para antes de 08/10/2026 (início da coleta).
- Snapshot repetido (mesma conta e mesmo `coletado_em`) **falha alto**.
- **Unidade:** seguidores; %; dias. **Limitações:** a série começa no primeiro snapshot (sem
  "antes da eleição" para seguidores — só para posts, §9.1); compra de seguidores e limpezas de
  contas falsas pela Meta geram saltos que não são efeito de campanha.
- Vetor: `vetores/serie_seguidores.json`

<a id="correlacao-redes"></a>
### 9.5 Correlação com o voto
- **Pares** (candidatos do **mesmo cargo**, contas com dados): seguidores × votos; engajamento
  mediano da campanha × votos; posts por semana na campanha × votos.
- **Estatística:** ρ de **Spearman** (postos médios nos empates) — robusto à cauda longa de
  seguidores e votos e invariante a transformações monotônicas: ρ(log seguidores, log votos) =
  ρ(seguidores, votos), então o log não muda o ρ (só o ajuste do §9.6).
- **IC 95 %:** *bootstrap* percentil pareado (Efron & Tibshirani 1993), **2000** reamostras com
  reposição dos candidatos, semente fixa **2026** (resultado reprodutível);
  `random.Random(semente).choices(range(n), k=n)` por réplica, um gerador novo por grupo, linhas
  em ordem de `sq_candidato`; réplica com variância zero é descartada (`n_bootstrap_validos`);
  quantis com interpolação linear.
- **n mínimo 10** pares: abaixo, ρ e IC `null` (a tela mostra "poucos candidatos"). Sempre
  publicar `n` e `n_excluidos` (contas sem dado ou valor nulo).
- **Recorte:** `por = cd_cargo` (padrão). Deputados de UFs diferentes disputam eleitorados de
  tamanhos muito diferentes: quando houver `n ≥ 10` numa UF, preferir `por = (cd_cargo, sg_uf)`
  ou trocar `votos` por **penetração** (§2.3) — a função aceita qualquer par de colunas.
- **Leitura obrigatória na tela:** correlação **não é causalidade** (candidato forte atrai
  seguidores, e não só o contrário); seguidores incluem não eleitores e outras UFs; contas sem
  dado ficam fora (contadas); três correlações sobre os mesmos candidatos são descritivas, sem
  correção de múltiplas comparações. Previsão de voto por redes tem histórico ruim
  (Gayo-Avello 2013); a associação existe, mas é confundida com o tamanho e a notoriedade do
  candidato (DiGrazia et al. 2013).
- Vetor: `vetores/correlacao_redes.json`

<a id="residuo-seguidores"></a>
### 9.6 Voto acima ou abaixo do esperado pelos seguidores (resíduo log-log)
- **Ajuste** por cargo (mínimos quadrados, contas com dados, n ≥ 10):
  `log10(1 + votos) = a + b · log10(1 + seguidores)`. O `1 +` mantém quem tem 0 votos ou 0
  seguidores; `b` (`inclinacao`) é a elasticidade: +1 % de seguidores ↔ +b % de votos.
- **Por candidato:** `votos_esperados = 10^(a + b·log10(1 + seguidores)) − 1`;
  `residuo_log10 = log10(1 + votos) − (a + b·log10(1 + seguidores))`;
  `razao_obs_esperado = 10^residuo_log10` (2 = o dobro do voto esperado para o tamanho da conta;
  0,5 = metade). Sem dado ou cargo com n < 10 → `null`.
- **Unidade:** votos; razão (escala log, divergente centrada em 1).
- **Limitações:** é um ajuste **descritivo** dentro do grupo, não um modelo de voto; com poucos
  candidatos um ponto extremo move a reta (MQO não é robusto) — mostrar n e a nuvem de pontos,
  não só o ranking. Mesmo cuidado de UF do §9.5.
- Vetor: `vetores/residuo_seguidores.json`

<a id="referencias"></a>
## 10. Referências
- Ames, B. (1995). Electoral strategy under open-list proportional representation. *American
  Journal of Political Science* 39(2): 406–433.
- Anselin, L. (1995). Local indicators of spatial association — LISA. *Geographical Analysis*
  27(2): 93–115.
- Avelino, G.; Biderman, C.; Silva, G. P. (2011). A concentração eleitoral nas eleições paulistas:
  medidas e aplicações. *Dados* 54(2): 319–347. doi:10.1590/S0011-52582011000200004.
- Avelino, G.; Biderman, C.; Silva, G. P. (2016). A concentração eleitoral no Brasil (1994-2014).
  *Dados* 59(4): 1091–1125.
- Silva, G. P.; Davidian, A. (2013). Identification of areas of vote concentration: evidences from
  Brazil. *Brazilian Political Science Review* 7(2). https://www.scielo.br/j/bpsr/a/xmLcsgG4hX5HFNHJwHr9BZp/
- Ellison, G.; Glaeser, E. (1997). Geographic concentration in U.S. manufacturing industries.
  *Journal of Political Economy* 105(5): 889–927.
- Laakso, M.; Taagepera, R. (1979). "Effective" number of parties. *Comparative Political Studies*
  12(1): 3–27.
- Hirschman, A. O. (1964). The paternity of an index. *American Economic Review* 54(5): 761 (HHI).
- Lei 9.504/1997 (Lei das Eleições), art. 23 §4º IV (financiamento coletivo como doação de pessoa física); arts. 16-C e 16-D (FEFC).
- Res. TSE 23.607/2019 (arrecadação, gastos e prestação de contas; recursos estimáveis; devolução de sobras do FEFC).
- Marshall, R. J. (1991). Mapping disease and mortality rates using empirical Bayes estimators.
  *Applied Statistics* 40(2): 283–294.
- Moran, P. A. P. (1950). Notes on continuous stochastic phenomena. *Biometrika* 37: 17–23.
- NCHS/CDC — critério de confiabilidade de taxas (< 20 eventos).
- Código Eleitoral (Lei 4.737/1965), arts. 106–109 e 175 §4º; Lei 14.211/2021 (cláusula de 10 % do QE).
- Spearman, C. (1904). The proof and measurement of association between two things. *American
  Journal of Psychology* 15(1): 72–101.
- Efron, B.; Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall
  (intervalo percentil, cap. 13).
- Gayo-Avello, D. (2013). A meta-analysis of state-of-the-art electoral prediction from Twitter
  data. *Social Science Computer Review* 31(6): 649–679.
- DiGrazia, J.; McKelvey, K.; Bollen, J.; Rojas, F. (2013). More tweets, more votes: social media
  as a quantitative indicator of political behavior. *PLoS ONE* 8(11): e79449.
- Constituição Federal, art. 77 (1º turno no primeiro domingo de outubro; 2º no último);
  Lei 9.504/1997, arts. 36 e 36-A (propaganda a partir de 16/08; pré-campanha); Decreto
  9.772/2019 (fim do horário de verão).
- Meta — Instagram Graph API, *Business Discovery* e *IG Media* (`like_count` omitido quando
  oculto): https://developers.facebook.com/docs/instagram-platform/
- Uber H3 — tabela de áreas por resolução: https://h3geo.org/docs/core-library/restable/
- BCB SGS 433 (IPCA, variação mensal): https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json
