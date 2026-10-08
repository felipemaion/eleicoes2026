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
