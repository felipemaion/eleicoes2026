# Handoff backend — T-B18 (API de redes sociais)

Branch `feat/backend-redes-sociais` (sobre `origin/main` 835dfa8; **sem push**). Commits: `test:` (fixtures +
testes vermelhos) → `feat:` → testes extras/varredura. Nenhuma fórmula local: tudo vem de `indicadores.redes`.

## Endpoints (OpenAPI regenerado: `docs/api/openapi.json`)
- `GET /api/redes?grupo&cargo&uf` — por candidato: `perfis` (username, link, `url_tse`, `principal` = 1º declarado ao
  TSE, `analisado` = conta usada nos indicadores, status, seguidores, seguindo, `n_midias`, `coletado_em`), `status`,
  `tem_dados`, razões seguidores×votos, ritmo (campanha/pós/variação), `pct_video`, engajamento mediano/médio,
  `janelas` (pré/campanha/pós/total com posts, vídeos, taxa semanal e engajamento) e `voto_esperado`
  (resíduo log-log). Mais `agregado` (n, seguidores, medianas), `excluidos` por motivo, `coletado_em`, `avisos`, `fontes`.
- `GET /api/redes/correlacoes?grupo&cargo&uf&por_uf` — por cargo (ou cargo×UF): 3 pares (`seguidores_votos`,
  `engajamento_votos`, `ritmo_votos`) com ρ, IC 95 %, `n`, `n_excluidos`, `n_minimo`; `ajuste` log-log; `pontos`
  (seguidores, votos, nome, `foto_url`, `link`, razão obs/esperado).
- `GET /api/redes/serie?sq=…|username=…` — pontos por perfil (seguidores, Δ abs/%, dias) + resumo; 404 `redes_sem_serie`
  se nenhum perfil tem seguidores coletados; `primeira_coleta`.
- Ficha `/api/candidatos/{ano}/{sq}`: campo `redes` (`perfis`, `coletado_em`, `fontes`). `perfis: []` = não declarou
  Instagram; `redes: null` = dado não publicado ou 2022.

## Decisões
1. **Perfil indisponível ≠ zero**: seguidores/seguindo/posts nulos + `status`. Quatro situações distintas:
   `sem_rede` (não declarou), `nao_coletado` (declarou, sem coleta), `nao_encontrado`/`nao_comercial`, `ok`.
   `excluidos` = {sem_instagram, nao_coletado, indisponivel, sem_votos}, **cada candidato em um só motivo**.
2. **Sem dado de redes → 503 `redes_indisponiveis`** (mensagem clara) nos 3 endpoints; a ficha segue funcionando com
   `redes: null`. Grupo que não é de 2026 → 422 `redes_ano_sem_dados`.
3. **`username` compartilhado por 2 candidaturas existe** (docs/fontes-de-dados.md). Os indicadores chaveiam por
   `username`, então o serviço usa a chave `"<sq>/<username>"` (e prefixa `media_id`) — senão `ultimo_snapshot`
   falharia por snapshot repetido e a dedupe de posts fundiria os candidatos. Coberto em `test_b18_correlacao.py`.
4. **ETag/cache**: novo `Repositorio.versao_dados()` = `dt_geracao` + `|` + última coleta de redes. ETag e cache
   LRU de `/redes*` e da ficha usam essa versão: a coleta é diária e **não muda o `DT_GERACAO`**, sem isso o navegador
   receberia 304 com redes velhas após reiniciar a API. Sem redes, `versao_dados() == dt_geracao()` (ETags antigos
   intactos). Os demais endpoints continuam com `dt_geracao`.
5. Textos públicos **não** estão na API: `avisos` devolve ids de `docs/metodologia/publico/textos.json`
   (`redes_nao_causalidade`, `redes_contas_sem_dados`, `redes_seguidores_sem_historico`). `redes_segundo_turno`
   fica para o front (depende do cargo).
6. Fontes: novo `FonteRede` (`Fonte` + `rotulo`): "Instagram — API oficial da Meta, coletado em DD/MM/AAAA" (data em
   Brasília; URL = doc Business Discovery, aberta e conferida em 08/10) e TSE `rede_social_candidato_AAAA.zip`.
7. Votos = `votos_totais` (nominais válidos). Candidato sem voto registrado → `votos: null` (razões nulas, fora das
   correlações, contado em `sem_votos`), não 0.
8. `por_uf=true` em `/correlacoes` agrupa cargo×UF (recomendação da spec §9.5 para deputados).

## Dados lidos (Parquet, `data/processed/`)
`redes_candidatos/ano=2026/`, `redes/redes_perfis.parquet`, `redes/redes_posts.parquet` (os 3 são necessários; basta
faltar um para virar 503). `coletado_em`/`timestamp` TIMESTAMPTZ → lidos como UTC naïve (sem `pytz`).

## Testes
`test_b18_redes.py` (44, DuckDB real sobre fixtures; as fixtures são validadas contra os contratos de `contratos.redes`),
`test_b18_correlacao.py` (n ≥ 10 conferido com **scipy**: ρ e reta log-log; username compartilhado),
`test_b18_memoria.py` (RepositorioMemoria: sem_votos, sem_instagram, 503), varredura cobre os 3 endpoints.
Fixtures: `apps/api/scripts/gerar_fixture.py` (+ `redes_*`).

## Atenção / pendências
- **Publicar**: `make publicar-dados` já envia `redes/` e `redes_candidatos/`; depois **reiniciar** (workflow Deploy) —
  a API só relê dados ao abrir. Antes disso `/api/redes*` responde 503 e a `varredura.py` contra produção reporta 5xx
  nesses endpoints (esperado até a publicação).
- Correlação: bootstrap de 2000 réplicas ≈ 0,3 s por par com n=300 (medido); cacheado por `versao_dados`.
- Aquecimento do cache não inclui redes (cálculo barato; 1ª chamada ~1 s no pior caso).
- `redes_segundo_turno` e a escolha de texto de `avisos` ficam com o frontend.
- Frontend: tipos saem do OpenAPI (`make openapi`); mudança é **aditiva** (campo `redes` na ficha, 3 rotas novas).

## Verificar
```bash
uv run pytest apps/api -k "b18 or varredura" -W ignore
make openapi && git diff --stat docs/api/openapi.json   # sem diff
uv run python -m api.openapi | head -0
```
