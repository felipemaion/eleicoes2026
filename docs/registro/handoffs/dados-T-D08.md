# Handoff dados — T-D08 · Redes sociais (URLs do TSE + coleta Instagram)

Branch `feat/dados-redes-sociais` (sobre `origin/main` 9513eb1; **sem push**). Testes: 765 Python verdes,
cobertura 95%; `ruff` + `mypy --strict` limpos. `eslint/vitest` não rodaram aqui (sem `node_modules` no
worktree; nada de `apps/` foi tocado).

## O que foi feito
- **Fonte TSE**: `consulta_cand/rede_social_candidato_AAAA.zip` (fora do `consulta_cand_AAAA.zip`), no catálogo
  como `rede_social_candidato`. `_BRASIL.csv` é a união das UFs: não é lido junto.
- **Parser** `etl.redes.url.username_instagram` (48 casos reais do cadastro). `@handle` solto vale como
  Instagram; post/reel/canal/`uid`/nome com espaço/outra rede → rejeitado.
- **`redes_candidatos`** (`etl redes-tse [--baixar]`): grupos `missao_2026` ∪ `mbl_2026` lidos de
  `config/grupos.yaml`. **548 candidatos · 544 com Instagram · 4 sem · 637 perfis** (74 candidatos têm >1
  perfil distinto: pessoal/campanha/partido). 8 URLs que citam Instagram foram rejeitadas.
- **Coleta** (`etl redes-coletar`, `make redes`): Business Discovery v26.0, conta descoberta via `me/accounts`,
  paginação até 01/01/2026 ou post já conhecido, cache por `(dia, username, cursor)`, backoff 4/17/32/613/80004,
  falha alto em token/permissão, status para perfil indisponível. Saídas `redes_perfis` (snapshots),
  `redes_posts` e `redes/manifesto.json` (versão da API, início/fim UTC, chamadas, perfis por status).
- **Token**: `debug_token` a cada coleta; ≤15 dias avisa (stderr), vencido falha. Hoje vence **07/12/2026**.
- **Divergências** (`etl redes-divergencias`): `data/reference/redes_divergencias_missao.csv` (83 linhas, sem
  CPF): 40 perfis diferentes · 16 site usa o perfil alternativo do TSE · 24 ausentes (ou sem Instagram) no
  site · 3 só no site.
- **Agendamento (não instalado)**: `scripts/redes-diario.sh` (retoma sozinho quando o ETL sai com 3 = limite)
  + `scripts/com.eleicoes2026.redes.plist` (03:00; instruções no cabeçalho do arquivo).
- Contratos em `packages/contratos/src/contratos/redes.py`; fontes documentadas em `docs/fontes-de-dados.md`.

## Rodada manual: 5 perfis reais (08/10/2026)
| username | status | seguidores | posts desde 01/01 | chamadas |
|---|---|---|---|---|
| kimkataguiri | ok | 2.456.122 | 1.138 | 23 |
| guilhermetedgue | ok | 9.760 | 70 | 2 |
| marcospinheirota | ok | 10.907 | 33 | 1 |
| renato_ristow | nao_encontrado | — | — | 1 |
| dr.joaoxavier | nao_encontrado | — | — | 1 |

**28 chamadas / 5 perfis** (3 ok · 2 `nao_encontrado` · 0 `nao_comercial`). Curtidas ocultas: 0 nos 1.241 posts
(vêm nulas quando ocultas). O uso do app foi de ~7% para ~19% com 28 chamadas (≈0,4%/chamada → ~230/h).

## Estimativa (extrapolada de 5 perfis — margem larga)
- **1ª rodada completa** (≈630 usernames): ~380 ok × ~2 páginas + ~10 contas grandes × ~10 + ~250
  indisponíveis × 1 ≈ **1.100 chamadas (faixa 900–1.500)** ≈ **5–8 h** no limite de ~200/h.
- **Diário depois**: ~380 ok × 1 + 1/7 dos indisponíveis (releitura semanal) ≈ **420 chamadas ≈ 2 h**.
- **Não rodei os 630**: aguardo o ok do orquestrador (brief). Comando: `scripts/redes-diario.sh`
  (ou `uv run etl redes-coletar`; repetível, retoma pelo cache do dia).

## Decisões e surpresas
1. **Vários perfis por candidato**: o contrato guarda todos (`principal` = menor `NR_ORDEM`); chave inclui
   `username`. Escolher "o perfil do candidato" quando houver conta de campanha/partido é decisão da análise.
2. **A API não distingue conta pessoal de inexistente** (mesma resposta 110/2207013): ambos viram
   `nao_encontrado`. `nao_comercial` só aparece se a mensagem disser. Para a tela: "perfil indisponível".
3. **Business Discovery não manda `paging.next`**, só `cursors.after` (corrigido após a 1ª rodada real parar
   na página 1; os testes agora imitam a API real).
4. Perfil indisponível é relido a cada 7 dias, não todo dia (economiza ~250 chamadas/dia).
5. `redes_posts` guarda a última leitura por post (não série de curtidas); `redes_perfis` é a série.
6. No site do Missão, "ausente" = candidato que não aparece ou não tem Instagram no JSON; é só conferência.

## Pendências / atenção
- **`scripts/publicar-dados.sh`** (não é meu) envia `data/processed/` com `--delete`: `redes/` e
  `redes_candidatos/` subirão junto; o backend precisa ler (`username`, `status`, `followers_count`…).
  `redes_candidatos.url_tse` é texto digitado pelo candidato (público no TSE).
- **Renovar o token antes de 07/12/2026.** Sem `META_APP_ID/SECRET` o aviso não roda (só avisa que não conferiu).
- Seguidores só têm histórico a partir do 1º snapshot (08/10/2026 — a rodada de teste já grava o de 5 perfis).
- `data/reference/redes_divergencias_missao.csv` foi gerado a pedido do brief (pasta é do Felipe).

## Como verificar
```bash
uv run pytest packages -q -k redes            # 100+ testes, sem rede
uv run etl redes-tse                          # usa data/raw/tse/rede_social_candidato (ou --baixar)
uv run etl redes-coletar --username kimkataguiri --limite 1   # 1 consulta/página real; precisa do .env
uv run etl redes-divergencias                 # baixa o site e regera o CSV
```
