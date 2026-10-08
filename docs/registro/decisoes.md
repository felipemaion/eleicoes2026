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
