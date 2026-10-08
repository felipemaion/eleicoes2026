# Decisões

| Data | Decisão | Por quê | Quem |
|---|---|---|---|
| 2026-10-07 | Escopo: Brasil inteiro, todos os cargos, filtro por UF/cargo na UI | evitar retrabalho; Missão concorreu em várias UFs | Felipe |
| 2026-10-07 | Mapa: MapLibre GL + D3 | zoom até local de votação; D3 para escalas/gráficos | Felipe (ADR 0001) |
| 2026-10-07 | Infra: DuckDB+Parquet, ETL local, Caddy serve estáticos | recomendação do Oracle; CPU escassa | Oracle (ADR 0002) |
| 2026-10-07 | Comparação temporal por município/H3 | rezoneamento; zona sem polígono | analise (ADR 0003) |
| 2026-10-07 | Lista MBL 2022 será fornecida por Felipe em `data/reference/` | fonte autoritativa do grupo | Felipe |
| 2026-10-07 | Repo público `felipemaion/eleicoes2026`, MIT, autoria só do Felipe | pedido explícito | Felipe (ADR 0006) |
| 2026-10-07 | 4 agentes (dados/analise Opus/backend/frontend) em tmux com worktrees | pedido; padrão do facc | orquestrador |
| 2026-10-07 | Repo público criado vazio; Issues #1–#17 abertas (labels papel/fase); push da `main` fica com o Felipe | Felipe preferiu publicar o código depois; a guarda pre-push não é contornada | Felipe |
| 2026-10-07 | Lista MBL 2022 = 4 indicados (Kim, Guto, Renato Battista, Cristiano Beraldo) + candidatos do Missão 2026 que disputaram 2022 (18 candidaturas); Beraldo entra também no grupo `mbl_2026` | pedido do Felipe | Felipe |
| 2026-10-07 | Grupo padrão `mbl_2022` = todas as 18 candidaturas (indicados + Missão 2026 que disputou 2022), mesmo quem não era MBL em 2022; recorte `mbl_2022_indicados` fica como filtro opcional | pedido do Felipe | Felipe |
| 2026-10-07 | PR #20 foi integrado com CI vermelho (falha do laço de merge); corrigido no #21 e criado `scripts/integrar.sh` (merge só com checks verdes) | incidente de processo | orquestrador |
| 2026-10-07 | Painéis dos agentes em `--permission-mode auto` | em `acceptEdits` cada heredoc travava num prompt manual; negações de push/PR/merge seguem por `--disallowedTools` | orquestrador |
| 2026-10-08 | Redesenho com a identidade do Missão (#fcbe26, #070d0c, branco), layout amplo, overlay e tooltip único | pedido do Felipe | Felipe |
| 2026-10-08 | Busca global, filtros dependentes, mapa focado na abrangência do candidato, evolução por pessoa | pedido do Felipe | Felipe |
| 2026-10-08 | Procedência em todo número (`fontes`) e links oficiais do TSE com `verificado`/nota | "tudo explicável e rastreável" | Felipe |
| 2026-10-08 | Fotos oficiais do TSE hospedadas no próprio servidor (WebP 160×200) | confiabilidade; TSE bloqueia scripts | orquestrador |
| 2026-10-08 | `pessoa_id` com sal único e guarda no manifesto | anos com sais diferentes zeravam a evolução por pessoa | dados |
| 2026-10-08 | Indicadores de receitas (T-A08/T-B14/T-W16) | pedido do Felipe | Felipe |
