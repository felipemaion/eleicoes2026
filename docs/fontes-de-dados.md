# Fontes de dados oficiais

Levantamento conferido em **2026-10-07** (agente de pesquisa de dados). Manter atualizado.

## TSE — Portal de Dados Abertos

Base CDN: `https://cdn.tse.jus.br/estatistica/sead/odsele/`

| Dataset | Caminho (ANO = 2022 \| 2026) | Uso |
|---|---|---|
| Candidatos | `consulta_cand/consulta_cand_{ANO}.zip` (CSV por UF + `_BRASIL`) | cadastro, partido, situação |
| Votação candidato | `votacao_candidato_munzona/votacao_candidato_munzona_{ANO}.zip` | votos por município×zona |
| Detalhe votação | `detalhe_votacao_munzona/detalhe_votacao_munzona_{ANO}.zip` | aptos, comparecimento, brancos, nulos |
| Votação partido | `votacao_partido_munzona/votacao_partido_munzona_{ANO}.zip` | votos de legenda |
| Votação por seção | `votacao_secao/votacao_secao_{ANO}_{UF}.zip` | densidade fina (por local) |
| Detalhe por seção | `detalhe_votacao_secao/detalhe_votacao_secao_{ANO}.zip` | aptos por seção |
| Locais de votação | `eleitorado_locais_votacao/eleitorado_local_votacao_{ANO}.zip` | lat/lon (`NR_LATITUDE`, `NR_LONGITUDE`) |
| Perfil eleitorado | `perfil_eleitorado/perfil_eleitorado_{ANO}.zip` | contexto (fase 2) |
| Prestação de contas | `prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ANO}.zip` | receitas, despesas contratadas/pagas |
| Códigos TSE↔IBGE | `municipio_tse_ibge/municipio_tse_ibge.zip` | crosswalk de municípios |

Tamanhos de referência: `votacao_candidato_munzona` 2026 ≈ 448 MB, 2022 ≈ 575 MB;
`votacao_secao_2026_SP` ≈ 770 MB.

### Formato e armadilhas
- Encoding **Latin-1**, separador `;`, textos entre aspas.
- Nulos: `#NULO`, `#NE`, e numéricos `-1`, `-3`. Decimal com vírgula (inclusive lat/lon).
- Datas `DD/MM/AAAA`. Coluna `DT_GERACAO`/`HH_GERACAO` em todos os arquivos.
- Código de eleição: 2026 → 6257 (federal), 6259 (estadual); 2022 → 544.
- Municípios em código **TSE** (5 dígitos) — sempre converter para IBGE (7 dígitos).
- `SQ_CANDIDATO` muda a cada eleição; ligar pessoas por CPF/título → `pessoa_id` (hash salgado).
- Arquivos de 2026 **regerados diariamente** e contas ainda **parciais** → manifesto com
  `DT_GERACAO` e sha256; rebaixar antes de publicar.
- DivulgaCandContas (API REST) bloqueia scripts (Akamai) — **não usar**.

### Alternativa em tempo real (só se necessário)
`https://resultados.tse.jus.br/oficial/ele2026/6259/...` (JSON de divulgação, por UF/município/cargo).

## Partido Missão
Registro deferido pelo TSE em 04/11/2025, número **14**. Em `consulta_cand_2026`: `NR_PARTIDO=14`,
`NM_PARTIDO="PARTIDO MISSÃO"`, ≈ 550 candidaturas (335 dep. federal, 162 dep. estadual,
14 distrital, 9 governador, 6 senador, 1 presidente).
Fonte: https://www.tse.jus.br/comunicacao/noticias/2025/Novembro/tse-aprova-registro-e-homologa-estatuto-do-partido-missao

## IBGE
- Malhas: `https://servicodados.ibge.gov.br/api/v3/malhas/estados/{UF}?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=minima`
  (também `paises/BR?intrarregiao=municipio`, TopoJSON com `formato=application/json`).
- Área territorial dos municípios (para votos/km² de contexto).

## BCB
- IPCA (SGS série 433) para deflacionar valores de 2022: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json`

## Zonas eleitorais
Não há polígono oficial. Aproximação: Voronoi dos locais de votação recortado pelo município;
município de zona única usa o próprio polígono. Chave `(cd_mun, nr_zona)`. Ver ADR 0003.

## Download (T-D01)
`uv run etl baixar --ano 2026 [--fonte ID ...] [--uf SP] [--forcar]` → `data/raw/` + `data/raw/manifesto.json`
(url, caminho, sha256, bytes, ETag, Last-Modified, baixado_em UTC). Idempotente: HEAD compara
ETag/Last-Modified; escrita em `.part` + rename atômico; retry (4 tentativas, backoff 1/2/4 s) só em
erro de rede/5xx. Catálogo: `packages/etl/src/etl/fontes/catalogo.py`.

## Processamento TSE → Parquet (T-D02)
`PESSOA_ID_SAL=<sal> uv run etl processar --ano 2022|2026 [--fonte ID ...]` → `data/processed/<fonte>/ano=<ano>/<UF>.parquet`
(`municipio_tse_ibge`, `consulta_cand`, `consulta_vagas`, `votacao_candidato_munzona`,
`detalhe_votacao_munzona`, `votacao_partido_munzona`, `eleitorado_local_votacao`). Contratos em
`packages/contratos/src/contratos/tse.py`; nomes = colunas do TSE em minúsculas + `cd_mun_ibge`,
`pessoa_id`. Medido: 2022 inteiro (4,3 GB de CSV de votação) em ~13 s e ~2,6 GB de RAM.

Armadilhas descobertas nos arquivos reais (2022 e 2026, layout idêntico):
- **Cada ZIP traz `_UF.csv` ×27, `_BR.csv` e `_BRASIL.csv`.** `_BR` = presidente (com `SG_UF` real);
  `_BRASIL` = união de todos (39.982 = 27.416 + 12.566 em `detalhe_votacao_munzona_2022`).
  Lê-se UF + `_BR` e **ignora-se `_BRASIL`**, senão tudo dobra.
- `CD_MUNICIPIO` vem sem zero à esquerda em alguns arquivos (`1007`) e com em outros (`"01007"`):
  sempre convertido a inteiro. Exterior (`SG_UF=ZZ`) não existe no crosswalk → `cd_mun_ibge` nulo.
- `consulta_vagas` usa `QT_VAGA` (singular), não `QT_VAGAS`.
- 2022: `CD_ELEICAO` 544 (pres. 1º turno), 545 (pres. 2º), **546 (estadual/federal)**, 547 (gov. 2º),
  6278 (suplementar, 48 linhas). 2026: 6257 (federal), 6259 (estadual).
- `nm_tipo_destinacao_votos` (valores distintos): 2022 = `Válido`, `Anulado`, `Anulado sub judice`,
  `Válido (legenda)`; 2026 = `Válido`, `Anulado sub judice`. **`qt_votos_nominais` ≠
  `qt_votos_nominais_validos`**: em `Anulado*` e `Válido (legenda)` os válidos são 0 (2022: 243.150
  votos "Válido (legenda)" têm `qt_votos_nominais_validos = 0`). Votos do candidato = coluna `_validos`.
- `votacao_partido_munzona`: um partido pode aparecer duas vezes na mesma zona com `SQ_COLIGACAO`
  diferentes (votos 0) → `sq_coligacao` faz parte da chave.
- `eleitorado_local_votacao` é por **seção** (≈989 mil linhas em 2022; turnos 1 e 2) → agregado para
  **local** (`qt_secoes`, soma de `qt_eleitor_secao`). Coordenada `(-1,0; -1,0)` = sem coordenada; locais
  do exterior ficam sem coordenada; coordenada fora do Brasil é anulada com aviso (2022: 1 local em
  MG, `(52051, zona 144, local 1023)`; 2026: MG, PA e RS, um cada).
- Nulos: `#NULO`/`#NE`/`#NI` em qualquer coluna; `-1`/`-3`/`-4` só em colunas inteiras.
  CPF/título `-4` = não divulgável → `pessoa_id` nulo.

## Prestação de contas e IPCA (T-D03)
`uv run etl baixar --ano 2022 --fonte prestacao_contas --fonte ipca` e
`uv run etl processar --ano 2022|2026 --dataset contas` / `uv run etl processar --dataset ipca`
→ `data/processed/{receitas_candidatos,despesas_contratadas_candidatos,despesas_pagas_candidatos}/ano=<ano>/<UF>.parquet`
e `data/processed/ipca/ipca.parquet`. Contratos em `packages/contratos/src/contratos/contas.py`.
Tempo medido: 2022 + 2026 (≈1,5 GB de CSV descompactado) em ~10 s.

O ZIP de cada ano traz, por dataset, `_UF.csv` ×27, `_BR.csv` (presidente) e `_BRASIL.csv` (união, ignorado
como em T-D02), além de `receitas_candidatos_doador_originario_*` (fora do escopo, também ignorado).

**Grão = lançamentos agregados**, não o lançamento cru: `SQ_RECEITA`/`SQ_DESPESA` **não são chaves** (2022:
674.944 linhas de receita para 665.131 pares prestador×receita; 301 linhas são cópias exatas) e o CSV traz CPF/nome
de doadores e fornecedores. O Parquet tem um registro por candidatura × prestação × rótulos, com
`vr_*` (soma), `qt_lancamentos` (nº de linhas do CSV) e `dt_geracao`. Totais de controle: soma em centavos
de `vr_*` e soma de `qt_lancamentos` = valores do CSV em texto. Nenhuma coluna de pessoa chega ao Parquet.

Armadilhas descobertas (2022 e 2026, layout idêntico):
- `ST_TURNO` (→ `nr_turno`) e `CD_ELEICAO` vêm em cada lançamento (2022: 544 presidente, 546 geral; 2026: 6257, 6259).
- **`SQ_PRESTADOR_CONTAS` ↔ `SQ_CANDIDATO` é 1:1** (2022: 27.958; 2026: 19.209 candidaturas com contas).
  `despesas_pagas` **não traz `SQ_CANDIDATO`**: o ETL liga pelo mapa de receitas + despesas contratadas do
  mesmo ano; prestador sem elo ou com 2 candidatos é **erro** (nos dados reais: 0 órfãos).
- Prestações (`tp_prestacao_contas`): 2022 = FINAL, PARCIAL, REGULARIZAÇÃO DA OMISSÃO, RELATÓRIO FINANCEIRO;
  2026 = FINAL, PARCIAL, RELATÓRIO FINANCEIRO. `dt_geracao` máxima: 2022 = 2026-10-04; 2026 = **2026-10-07**
  (**contas de 2026 parciais**: 1.350 FINAL, 256.000 PARCIAL, 410.711 RELATÓRIO FINANCEIRO nas pagas).
- Rótulos nulos (`#NULO`) são linhas **de valor R$ 0,00** (sem movimento): receitas com fonte/origem nulas
  (2022: 2.979; 2026: 2.421) e despesas contratadas com origem nula (2022: 4.946; 2026: 4.544). Ficam no
  Parquet (o total de linhas bate), mas `classificar_receitas` rejeita `None`: **filtrar `vr = 0`/nulos antes**.
- Valores são decimais com vírgula, podem ser negativos (estorno); somados com sinal.
- Rótulos `ds_*` seguem **brutos**: o ETL só apara e colapsa espaços (caixa e acento intactos); a classificação
  é de `indicadores.financeiro`.

### Valores distintos (lançamentos por rótulo; insumo para fechar a tabela de classificação)
`ds_fonte_receita` — 2022: OUTROS RECURSOS 567.864 · FUNDO ESPECIAL 88.228 · FUNDO PARTIDARIO 15.873 · nulo 2.979.
2026: OUTROS RECURSOS 116.940 · FUNDO ESPECIAL 37.663 · FUNDO PARTIDARIO 14.330 · nulo 2.421.

`ds_origem_receita` — comuns: Recursos de pessoas físicas · Recursos de partido político · Recursos de outros
candidatos · Recursos próprios · Recursos de Financiamento Coletivo · Recursos de origens não identificadas ·
Doações pela Internet · nulo. Só em **2022**: Rendimentos de aplicações financeiras (569) · Comercialização de
Bens com OR (138) · Comercialização de Bens com FEFC (4). Só em **2026** (novos): **Fundo Especial de
Financiamento de Campanha (46) · Fundo Partidário (5) · Doações para Campanha (31)** — a *origem* repete o nome
de um fundo e "Doações para Campanha" não existe em 2022.

`ds_natureza_receita` — FINANCEIRO · ESTIMÁVEL (2022: 539.581 / 135.363; 2026: 108.160 / 63.194).

`ds_fonte_despesa` (pagas) — Fundo Especial de Financiamento de Campanha · Outros Recursos · Fundo Partidário.

`ds_origem_despesa` (contratadas e pagas; 2022 = 41 rótulos, 2026 = 42 + nulo nas contratadas): Atividades de
militância e mobilização de rua · Despesas com pessoal · Encargos financeiros, taxas bancárias e/ou op. cartão de
crédito · Publicidade por materiais impressos · Combustíveis e lubrificantes · Serviços prestados por terceiros ·
Publicidade por adesivos · Cessão ou locação de veículos · Alimentação · Despesa com Impulsionamento de Conteúdos ·
Materiais de expediente · Diversas a especificar · Correspondências e despesas postais · Serviços contábeis ·
Serviços advocatícios · Locação/cessão de bens imóveis · Publicidade por jornais e revistas · Produção de
programas de rádio, televisão ou vídeo · Despesas com transporte ou deslocamento · Produção de jingles, vinhetas
e slogans · Locação/cessão de bens móveis (exceto veículos) · **Doações financeiras a outros candidatos/partidos**
(repasse, não custo — spec §4.2) · Serviços próprios prestados por terceiros · Despesas com Hospedagem · Criação
e inclusão de páginas na internet · Eventos de promoção da candidatura · Publicidade por carros de som · Taxa de
Administração de Financiamento Coletivo · Água · Pré-instalação física de comitê de campanha · Impostos,
contribuições e taxas · Comícios · Energia elétrica · Pesquisas ou testes eleitorais · Passagem Aérea ·
Aquisição/Doação de bens móveis ou imóveis · Telefone · Reembolsos de gastos realizados por eleitores · Encargos
sociais · Despesa com geradores de energia · Multas eleitorais. Só em **2026**: *Segurança e prevenção,
repressão e combate à violência política*.

### IPCA (BCB SGS 433)
`ipca.parquet`: `mes` ("AAAA-MM"), `variacao` (% mensal, como o BCB publica) e `indice` (acumulado, base 100
em dez/1979). Fator entre meses = `indice[base]/indice[origem]` (= Π(1+v/100), vetor `deflacao_ipca`). Mês
faltante/repetido na série **falha** o processamento. Última observação baixada em 2026-10-07: **2026-08**
(set/2026 sai ≈ 09/10/2026; a emenda do ADR 0007 manda usar o último mês disponível como base).
