# Handoff — analise · T-A10 (indicadores de redes sociais e correlação com voto)

Branch `feat/analise-redes-sociais` (a partir de `origin/main` 9513eb1). Commits:
`docs(metodologia): spec…` → `test(indicadores): …` (vermelho: `redes` inexistente) →
`feat(indicadores): …` (verde). `make lint test` verde (py 701 passed; web 33 arquivos / 344 testes).

## O que foi feito
1. **Spec** `docs/metodologia/indicadores.md` §9 "Redes sociais (Instagram)" (Referências viraram
   §10): decisões comuns (§9.0) e seis indicadores, cada um com vetor em
   `docs/metodologia/vetores/`: `ritmo_posts`, `engajamento`, `seguidores_votos`,
   `serie_seguidores`, `correlacao_redes`, `residuo_seguidores`. Vetores gerados por uma
   referência independente em Python puro (sem polars) e conferidos à mão.
2. **Código** `packages/indicadores/src/indicadores/redes.py` (polars→polars, sem I/O):
   - `metricas_janelas(perfis, posts)` → conta × janela (`pre_campanha`, `campanha`,
     `pos_eleicao`, `total`): `dias`, `n_posts`, `n_videos`, `posts_por_semana`,
     `videos_por_semana`, `pct_video`, `n_posts_engajamento`, `engajamento_medio/mediano`.
   - `indicadores_candidato(perfis, posts, votos)` → uma linha por candidatura (inclusive sem
     conta: `status = sem_rede`, `tem_dados = false`), com seguidores, `seguidores_por_mil_votos`,
     `votos_por_mil_seguidores`, ritmo campanha/pós e `variacao_ritmo_pct`, `pct_video`,
     engajamento da campanha.
   - `serie_seguidores` / `resumo_serie_seguidores` (variações só com ≥ 2 snapshots válidos).
   - `correlacao(df, x, y, por=("cd_cargo",), n_bootstrap=2000, nivel=0.95, semente=2026)` →
     `n, n_excluidos, rho, ic_inf, ic_sup, n_bootstrap_validos` (n < 10 → nulos).
   - `residuo_log(df, x="seguidores", y="votos")` → `intercepto, inclinacao, votos_esperados,
     residuo_log10, razao_obs_esperado`.
   - Spearman movido para `_comum.spearman_listas` (reusado por `evolucao.spearman`, sem mudança
     de comportamento).
3. **Conferência com scipy** (`tests/test_redes.py`): ρ = `spearmanr` (1e-12); IC bootstrap a
   ≤ 0,03 do `scipy.stats.bootstrap` percentil pareado (geradores diferentes); ajuste = `linregress`
   (1e-10); ρ invariante ao log; reprodutibilidade da semente; datas sem fuso = UTC.
   `scipy` entrou no grupo `dev` do `pyproject.toml` raiz (+ `uv.lock`) — só para teste; o pacote
   `indicadores` continua só com polars.
4. **Textos públicos** `textos.json`: 6 indicadores, tela nova `redes` (rodapé com
   `{dt_coleta_redes}`, placeholder global novo), avisos `redes_nao_causalidade`,
   `redes_contas_sem_dados`, `redes_seguidores_sem_historico`, `redes_segundo_turno`; glossário
   `engajamento`, `reels`, `conta_comercial`, `correlacao_spearman`, `pre_campanha`.
   README público: seção "Redes sociais".

## Decisões metodológicas (na spec §9.0; candidatas a ADR se o orquestrador quiser)
- Datas no **fuso de Brasília**: post às 23h30 de 04/10 é campanha (02h30 UTC de 05/10).
- Janelas: pré 01/01–15/08 (227 d), campanha 16/08–04/10 (50 d), pós 05/10 → última coleta da
  conta (dias fracionários), total 01/01 → última coleta. **Taxa semanal nula com < 7 dias**
  (hoje, 08/10, o pós tem ~3 dias: `posts_semana_pos` e `variacao_ritmo_pct` ficam nulos até
  ~12/10 — esperado, não bug).
- Engajamento = 100 × (curtidas + comentários)/seguidores do último snapshot; fora: curtidas
  ou comentários nulos e posts com < 48 h na coleta. Resumo do candidato usa a **campanha**.
- Vídeo = `media_type = VIDEO` (inclui reels); carrossel conta como post.
- Conta principal = mais seguidores (empate: username). Conta "com dados" = `followers_count`
  não nulo (não depende do nome exato do `status`).
- Correlação: Spearman (log não muda ρ), IC bootstrap percentil 2000 réplicas, semente 2026,
  n mínimo 10. Resíduo: MQO em log10(1+x).

## Pendências / para outros papéis
- **dados (T-D08):** a spec assume `redes_perfis(sq_candidato, username, status,
  followers_count, follows_count, media_count, coletado_em)` e `redes_posts(username, media_id,
  timestamp, media_type, media_product_type, like_count, comments_count, coletado_em)`, datas
  `Datetime` UTC (sem fuso é aceito como UTC). O schema do T-D08 ainda não estava no `main`;
  se os nomes mudarem, ajustar `redes._COLUNAS_*` e os adaptadores do teste.
- **backend:** `correlacao` com 2000 réplicas é Python puro — ~1–3 s para algumas centenas de
  candidatos; calcular uma vez por coleta e cachear, não por requisição. Votos = nominais
  válidos (§2.1) do mesmo cargo. Para deputados, oferecer `por=("cd_cargo","sg_uf")` ou
  `y="penetracao"` quando n ≥ 10 (UFs de tamanhos diferentes; spec §9.5).
- **frontend:** tela `redes` em `textos.json`; mostrar `n` e `n_excluidos` ao lado de cada ρ;
  razão do resíduo em escala log divergente centrada em 1; nuvem de pontos junto do ranking.

## Como verificar
```bash
uv run pytest packages/indicadores -q -k "redes or ritmo or engajamento or seguidores or correlacao or residuo or textos"
make lint test
```
