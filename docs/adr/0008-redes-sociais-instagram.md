# ADR 0008 — Redes sociais: Instagram via API oficial da Meta (exceção às fontes TSE/IBGE/BCB)

- **Status:** aceita (08/10/2026, decisão do Felipe)
- **Contexto:** pedido de uma aba com análises e correlações dos candidatos do Partido Missão 2026 e das suas redes
  sociais (seguidores, posts e vídeos antes e depois da eleição). A regra do projeto é usar só fontes oficiais
  (TSE, IBGE, BCB). Métricas de redes sociais só existem na própria plataforma.

## Decisão
1. **Quais perfis:** as URLs vêm do **TSE** (redes sociais declaradas no registro de candidatura, fonte oficial).
   O site `candidatos.missao.org.br` serve **só para conferência** (lista divergências; não é fonte de dado publicado).
2. **Métricas:** só da **API oficial da Meta** — Instagram Graph API, endpoint **Business Discovery**, com o app
   "Painel Eleitoral 2026" em modo de desenvolvimento (uso próprio, sem análise da Meta). Nada de raspagem de páginas.
   Permissões do token: `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`,
   `business_management`, `ads_read`. Credenciais em `.env` (`META_APP_ID`, `META_APP_SECRET`, `META_TOKEN`), fora do git.
3. **Escopo da 1ª versão:** só **Instagram**. Facebook (páginas de terceiros) exige revisão da Meta — fica para depois.
4. **Antes × depois:** posts/vídeos têm data → contagem por janela a partir do `timestamp`. **Seguidores não têm
   histórico** na API: a série começa no primeiro snapshot (08/10/2026) — nunca inventar valor anterior.
5. **Rastreabilidade:** cada snapshot guarda data/hora da coleta, versão da API e o `username` consultado; a tela
   cita "Instagram (API oficial da Meta), coletado em DD/MM/AAAA".

## Limitações (aparecem na tela)
- Business Discovery só lê contas **comerciais ou de criador**; contas pessoais ficam só com o link.
- Não há visualizações de vídeos de terceiros; curtidas podem estar ocultas (vêm ausentes — nulo, não zero).
- Limite de ~200 chamadas/hora por token: coleta incremental com cache em disco.
- Token de longa duração vence em ~60 dias (atual: **07/12/2026**); renovar antes (o ETL avisa com 15 dias).
- Correlação com voto não é causalidade; seguidores incluem não eleitores e outras UFs.
