# Handoff dados — T-D02 (contratos Parquet + parsers TSE)
Branch `feat/dados-parsers` (a partir de `feat/dados-downloader`; **depende do PR da T-D01**).

## O que foi feito
- `packages/contratos`: `Contrato` + `validar()` (colunas, tipos, chave única, nulos, faixas; lazy) e 7
  contratos (`tse.py`) com os nomes do **mapa de colunas** da spec (minúsculas) + `cd_mun_ibge`.
- `etl/tse_csv.py`: único lugar de encoding/nulos/decimal/data (Latin-1 transcodificado em pedaços,
  `scan_csv` em streaming, conversão estrita — valor inválido ou coluna ausente falha).
- `etl/processar.py` + `etl processar --ano`: por membro do ZIP: ler → ligar IBGE → regra → gravar `.tmp`
  → **contrato + total de controle** (soma e nº de linhas contra a origem) → só então `rename`.
  Município sem correspondência no crosswalk falha alto (exceto ZZ). `dt_geracao` volta ao manifesto.
- `pessoa_id = sha256(sal ‖ cpf)` (ADR 0004; cai no título; `-4` → nulo); CPF/título/e-mail não chegam
  ao Parquet. Sal só por `PESSOA_ID_SAL`.
- Fixtures reais (Bujari e Capixaba/AC, 2022) + `gerar_fixtures.py` (CPF/título **sintéticos**).
- Rodei **2022 e 2026 inteiros** localmente: todos os contratos e totais passaram.

## Respostas às pendências da análise (T-A01)
- `consulta_vagas`: caminho `consulta_vagas/consulta_vagas_{ANO}.zip`; coluna **`qt_vaga`**.
- `CD_ELEICAO` 2022 estadual = 546 confirmado; valores de `NM_TIPO_DESTINACAO_VOTOS` em
  `docs/fontes-de-dados.md`. **Votos do candidato = `qt_votos_nominais_validos`** (≠ `qt_votos_nominais`).
- `despesas_pagas` por `SQ_PRESTADOR_CONTAS` e listas de `DS_FONTE/ORIGEM_*`: ficam na **T-D03**
  (prestação de contas). Tabela AMC: não feita (fora desta tarefa).

## Decisões / pontos de atenção
- `_BRASIL` ignorado (é a união); `_BR` = presidente. Detalhes em `docs/fontes-de-dados.md`.
- `votacao_partido_munzona`: `sq_coligacao` entra na chave (duplicidade real do TSE, votos 0).
- Locais agregados de seção → local; coordenadas inválidas viram nulas com aviso (1–3 por ano).
- `ErroProcessamento`/`ContratoViolado` sem sufixo `Error` (noqa N818) — nomes de domínio.
- Esta tarefa não cobre `votacao_secao`/`detalhe_votacao_secao` (H3 por seção) nem IBGE/BCB.

## Verificar
`make lint test` (verde; cobertura etl ≈ 96–100%). Dados reais:
`PESSOA_ID_SAL=$(...) uv run etl baixar --ano 2022 && uv run etl processar --ano 2022`.

## Revisão (PR #29) — correções aplicadas
1. **Privacidade:** o CSV transcodificado (com CPF/título) vive em `tempfile.mkdtemp` (sistema, 0700), fora de
   `processed/`, e o `.utf8.csv` é apagado ao fim de cada membro (`finally`). Teste espiona `hash_pessoa` e
   prova que nada com CPF existe sob `processed/` enquanto o CSV existe fora dele; nada sobra no fim.
2. **`hash_pessoa`:** CPF só com 11 dígitos, DV válido e não repetido; título só com 12 dígitos não repetidos;
   o resto → `None`. Fixture `consulta_cand` regenerada com CPFs sintéticos de DV válido.
3. **Total de controle não circular:** esperado vem do CSV **em texto** (`scan_texto`, cast não estrito, soma
   de valores ≥ 0); sentinelas e não numéricos por coluna vão ao log (INFO). Teste com `-1`/`-3`.
4. **`_agregar_locais`:** ordena por turno e `nr_secao`, `group_by(maintain_order=True)`; lat/lon vêm de UMA
   mesma seção (struct) e metade de coordenada é anulada. Teste com 3 ordens de linhas → mesmo resultado.
5. **Publicação atômica:** todos os membros validados em `ano=N.tmp/`, depois troca de diretório
   (`ano=N.old` → apaga). Falha em qualquer membro mantém o ano anterior intacto. Teste incluso.
- `make lint test`: lint verde; pytest 174 passed, cobertura 96%. `vitest` falha só por `node_modules`
  ausente neste worktree (ambiente, não código).
- Reprocessados 2022 e 2026 (tudo exceto `consulta_cand`): contratos e totais OK. `consulta_cand` foi
  validado com sal descartável em diretório temporário; **rode-o com o `PESSOA_ID_SAL` real** para
  regenerar `data/processed/consulta_cand` (o `pessoa_id` mudou de regra: CPF inválido agora é nulo).
