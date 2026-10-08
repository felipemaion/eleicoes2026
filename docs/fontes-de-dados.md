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
- **Malha municipal**: shapefile oficial `BR_Municipios_2025.zip` (Malha Municipal Digital 2025, 237 MB,
  5.571 municípios, campo `CD_MUN`) em
  `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/Brasil/`.
  **Não** usamos a API v3 de malhas: ela não traz Boa Esperança do Norte/MT (município novo) e
  ainda desenha Sorriso/Nova Ubiratã com o território antigo. Lido com `pyshp` e simplificado
  (0,0005° ≈ 50 m) — fonte `malha_municipios`.
- **UFs**: `api/v3/malhas/paises/BR?intrarregiao=UF&qualidade=intermediaria` — fonte `malha_ufs`.
- **Área territorial**: `.../estrutura_territorial/areas_territoriais/2025/AR_BR_RG_UF_RGINT_RGI_MUN_2025.xls`
  (aba `AR_BR_MUN_2025`, km², calculada sobre a mesma malha 2025) — fonte `areas_ibge`. Traz 5.571
  municípios + 2 "Áreas Operacionais" das lagoas (RS, `43000xx`), descartadas.
- **AMC 2022↔2026**: o IBGE só publica AMC censitária (até 2010). Para 2022→2026 há **um** desmembramento:
  Boa Esperança do Norte/MT (5101837; Lei MT 7.264/2000, validada pelo STF em out/2023, entrou na DTB 2024),
  saída de **Sorriso (5107925) e Nova Ubiratã (5106240)**. Verificado nos dados: é o único código de 2026
  ausente de `eleitorado_local_votacao` 2022. `cd_amc` = menor código do grupo (5101837). Lista em
  `etl.municipios.AGREGACOES_AMC`.

## Geo (T-D04)
`uv run etl baixar --ano 2026 --fonte areas_ibge --fonte malha_municipios --fonte malha_ufs` e depois
`uv run etl geo` → `data/processed/municipios.parquet` (contrato `municipios`) e
`data/processed/tiles/municipios.<hash12>.pmtiles` + `tiles/manifesto.json` (`arquivo`, `sha256`, `camadas`).
Camadas (zoom 3–10): `ufs` (`cd_uf`, `sg_uf`), `municipios` (`cd_mun_ibge` int, `nm`),
`zonas_2022` e `zonas_2026` (`cd_mun_ibge`, `nr_zona`, `id` = `<cd_mun_ibge>-<nr_zona>`).
Limitações das zonas (aproximação, ADR 0003): locais sem coordenada no TSE (7% em 2022) ficam fora do
Voronoi; zona sem nenhum local georreferenciado **não ganha polígono** (251 em 2022, 1 em 2026) e as
vizinhas ocupam o espaço dela. Em 2022, locais dentro do território hoje de Boa Esperança do Norte caem
fora do polígono de Sorriso/Nova Ubiratã e são descartados.

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
**Um sal só para todos os anos** (T-D06): o manifesto guarda `sal_impressao = sha256(sal)[:12]` por arquivo e `etl processar` falha se outro ano de `consulta_cand` tiver impressão diferente. Mudou o sal? Reprocesse 2022 e 2026.
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

## Votação por seção → local → H3 (T-D05)
`uv run etl secao --ano 2022|2026 [--uf AC ...] [--baixar] [--descartar-zip]` →
`data/processed/{votos_local,totais_local}/ano=<ano>/<UF>.parquet` e
`data/processed/locais_h3/ano=<ano>/locais_h3.parquet`. Contratos em `contratos/tse.py`
(`votos_local`, `totais_local`, `locais_h3`; `votacao_secao` é só o esquema de leitura).

- **Arquivos**: `votacao_secao_{ANO}_{UF}.zip` ×27 + `_BR` (presidente, cargo 1; cada linha traz a UF real,
  exterior = `SG_UF` ZZ). 2022 **não tem** `_ZZ` (404; o exterior vem em `_BR`); `votacao_secao_2026_ZZ.zip`
  existe mas só tem o cabeçalho (sem linhas) enquanto não houver votação no exterior — tratado como vazio.
  Tamanhos: SP 2022 = 901 MB zip (≈ 10 GB de CSV), BR 2022 = 271 MB, BR 2026 = 162 MB (1 GB de CSV).
- **Leitura em blocos** (`tse_csv.blocos_utf8`, 256 MB): nunca há cópia UTF-8 do CSV inteiro (o disco local
  tem ~6 GB livres). `--descartar-zip` apaga cada ZIP depois de validado (sha256 segue no manifesto) e
  `--baixar` baixa UF a UF.
- **Colunas** (26): `DT_GERACAO … SG_UF, SG_UE, CD_MUNICIPIO, NR_ZONA, NR_SECAO, CD_CARGO, NR_VOTAVEL, NM_VOTAVEL,
  QT_VOTOS, NR_LOCAL_VOTACAO, SQ_CANDIDATO, NM_LOCAL_VOTACAO, DS_LOCAL_VOTACAO_ENDERECO`. **Sem coordenada**:
  lat/lon vêm do `eleitorado_local_votacao` (mesma chave município TSE × zona × local).
- **`SQ_CANDIDATO`**: `> 0` = voto no candidato; `-3` = voto de legenda (`NR_VOTAVEL` = nº do partido);
  `-1` = branco (`NR_VOTAVEL` 95) ou nulo (96). Os cargos de uma seção somam o mesmo comparecimento.
- **Só 1º turno** em `votos_local`/`totais_local`/`locais_h3` (a API não filtra turno nessas tabelas;
  o contrato trava `nr_turno = 1`). 2º turno 2022 (presidente/governador) é ignorado e contado em
  `linhas_turno2_ignoradas`.
- **`votos_local` = votos nominais (`qt_votos_nominais`)**, não os "válidos" do munzona: o arquivo por seção não
  separa anulados sub judice (`qt_votos_nominais_validos` do munzona é menor para esses candidatos).
- **Total de controle (por UF, antes de publicar)**: (1) linhas lidas = `\n` do fluxo, bloco a bloco;
  (2) Σ `qt_votos` do texto cru (1º turno) = nominais + legenda + brancos + nulos; (3) Σ `votos_local` =
  `totais_local.votos_nominais`; (4) **para todo candidato que está no `votacao_candidato_munzona`,
  Σ locais = `qt_votos_nominais` do munzona** (diverge → erro). O arquivo por seção também traz candidaturas
  que **não** estão no munzona (candidatura anulada/indeferida, votos descartados): contadas em
  `candidatos_fora_do_munzona`/`votos_fora_do_munzona` e mantidas em `votos_local`.
- **`locais_h3`**: um registro por local do 1º turno **com coordenada válida** (`h3` = res 8 canônica, `h3_r7`,
  `h3_r6` por `cell_to_parent`; `aptos` = `qt_eleitor_secao` do local). Local sem coordenada (inclui exterior) fica
  **fora** (nunca no centróide, ADR 0007). `h3` é o nome que a API lê; o brief chamava de `h3_r8`.
- Nomes alinhados ao backend: `nr_local` (não `nr_local_votacao`) e `ano` pela partição hive `ano=AAAA/`.

## Fotos dos candidatos (T-D07)
- **URL** (outra árvore do CDN, não `odsele`):
  `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ANO}/fotos/foto_cand{ANO}_{UF}_div.zip`,
  por UF + `BR` (presidente). **Sem ZIP de `ZZ`** em 2022 nem 2026 (404 verificado em 2026-10-08).
  Tamanhos: 2026 ≈ 15 MB (SP), 2022 ≈ 90 MB (SP); total ≈ 245 MB em `data/raw/tse/fotos/`.
- **Conteúdo**: `F<UF><SQ_CANDIDATO>_div.jpg|jpeg` (as duas extensões aparecem) + `leiame.pdf`; JPEG de
  tamanhos variados (ex. 161×225, 111×155). A chave é o `sq_candidato` (Int64 no Parquet, texto no nome).
- **Cobertura**: nem todo candidato tem foto (2026: 1 de 20.302; 2022: 25 de 28.720 — quase todos INAPTOS).
- **Processamento** (`etl fotos --ano A [--baixar] [--uf UF]`): seleciona cargos 1–8 (+ todo o partido 14
  em 2026), recorta para 160×200 (proporção 4:5, âncora no topo para preservar o rosto), WebP q70, em
  `data/processed/fotos/<ano>/<sq>.webp` + `fotos/manifesto.json` (`sq` → `arquivo`, `origem`, `sha256`,
  `sha256_origem`). Idempotente pelo sha256 do JPEG de origem. Servido em `/fotos/<ano>/<sq>.webp`.

## Redes sociais: Instagram (T-D08, ADR 0008)
Única exceção à regra "só TSE/IBGE/BCB": as **métricas** vêm da API oficial da Meta; os **perfis** vêm do TSE.

### URLs declaradas (TSE) → `redes_candidatos`
- **Arquivo**: `https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_{ANO}.zip`
  (fonte `rede_social_candidato`; **não** está dentro de `consulta_cand_AAAA.zip`). Contém
  `rede_social_candidato_AAAA_<UF>.csv` (+ `_BR`), `_BRASIL.csv` (**união** dos anteriores: não ler junto) e
  `leiame.pdf`. Colunas: `DT_GERACAO, HH_GERACAO, AA_ELEICAO, SG_UF, CD_TIPO_ELEICAO, NM_TIPO_ELEICAO,
  CD_ELEICAO, DS_ELEICAO, SQ_CANDIDATO, NR_ORDEM_REDE_SOCIAL, DS_URL`. 2026 (08/10): 63.213 linhas.
- **`DS_URL` é texto livre, sem validação**: URL com `?igsh=`/`utm_`, `@handle`, `INSTAGRAM: handle`,
  `handle - instagram`, caixa alta, `instagran`, links de post/reel/canal/`uid`, nomes com espaço e outras
  redes. Uma linha por URL; o candidato pode declarar vários perfis (pessoal, campanha, partido).
- **Parser** (`etl.redes.url.username_instagram`): devolve o username (minúsculo, sem `@`, 1–30 de
  `[a-z0-9._]`) só se o texto aponta para **um perfil** do Instagram; rejeita post/reel/canal/`uid`/stories,
  nome com espaço, texto que cite outra rede e qualquer ambiguidade. `@handle` solto é aceito como Instagram
  (é o uso dominante no cadastro); `@handle (tiktok)` não.
- **Saída** `data/processed/redes_candidatos/ano=AAAA/redes_candidatos.parquet`: uma linha por
  candidatura × perfil distinto dos grupos `missao_2026` ∪ `mbl_2026` (lidos de `config/grupos.yaml`, Beraldo
  incluído). `principal` = o de menor `NR_ORDEM_REDE_SOCIAL`; os demais ficam (`principal = false`) para a
  análise decidir. Chave `(ano_eleicao, sq_candidato, rede, username)`. Sem CPF.
- **2026-10-08**: 548 candidatos nos grupos · 544 com Instagram · 4 sem · 637 perfis (74 candidatos com mais
  de um perfil) · 8 URLs que citam Instagram rejeitadas. Um mesmo `username` pode ser de dois `sq`
  (registros duplicados da mesma pessoa): a coleta gasta uma consulta e grava um snapshot por `sq`.
- **Conferência** (`etl redes-divergencias`): compara com `candidatos.missao.org.br` — o HTML (Next.js)
  embute a lista como JSON (`sq`, `instagram`, `seguidores`). **Só relatório** em
  `data/reference/redes_divergencias_missao.csv`; o site nunca alimenta dado publicado.

### Coleta (Instagram Graph API, Business Discovery)
- **Credenciais**: `.env` (`META_TOKEN`, `META_APP_ID`, `META_APP_SECRET`), fora do git. O token vai no
  cabeçalho `Authorization: Bearer`, **nunca na URL** nem em log/manifesto/fixture (única exceção da própria
  API: `debug_token` aceita `input_token` só na query; o cliente não imprime URLs).
- **Conta do app**: descoberta por `GET me/accounts?fields=instagram_business_account` (id não fica no código).
- **Chamada**: `GET /v26.0/{ig_id}?fields=business_discovery.username(U){username,name,biography,
  followers_count,follows_count,media_count,media.limit(50)[.after(C)]{id,timestamp,media_type,
  media_product_type,like_count,comments_count,permalink}}`.
- **Paginação**: a Business Discovery **não manda `paging.next`**, só `paging.cursors.after` (ausente na
  última página). Páginas vêm da mais nova para a mais antiga; para-se ao cruzar 01/01/2026 ou ao alcançar um
  post já conhecido (reler a 1ª página atualiza curtidas/comentários dos recentes).
- **Erros**: código 110/100 (subcódigo 2207013) = perfil **inexistente ou pessoal** — a API **não
  distingue** os dois (mesma resposta); vira `nao_encontrado` (`nao_comercial` só se a mensagem disser).
  Perfil indisponível é relido a cada 7 dias (não gasta chamada diária). 190/102/10/2xx = token/permissão →
  **falha alto**. 4/17/32/613/80004 = limite → backoff 60·2ⁿ s; persistindo, sai com código 3 (retomável).
  O uso do app vem em `x-app-usage.call_count` (% da janela de 1 h): ≥95% pausa 5 min antes da próxima.
- **Cache**: cada resposta em `data/raw/meta/AAAA-MM-DD/<username>/<cursor>.json`; repetir no mesmo dia não
  chama a API nem duplica linhas.
- **Saídas** (`data/processed/redes/`): `redes_perfis.parquet` (um registro por coleta — **série de
  snapshots**; a API não tem histórico de seguidores de terceiros, a série começa em 08/10/2026),
  `redes_posts.parquet` (um registro por `(username, media_id)`, com a última leitura; `like_count` nulo
  quando oculto, nunca zero) e `manifesto.json` (por rodada: início/fim UTC, `versao_api`, chamadas, perfis
  por status). Posts só desde 01/01/2026. `timestamp`/`coletado_em` em UTC.
- **Token**: vence em 07/12/2026. A cada coleta, `debug_token` confere; ≤15 dias avisa no stderr, vencido falha.
- **Rodar**: `make redes` (TSE + coleta). Diário: `scripts/redes-diario.sh` + `scripts/com.eleicoes2026.redes.plist`
  (instruções no próprio arquivo; **não instalar sem o orquestrador**).
