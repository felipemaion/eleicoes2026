# Handoff backend — T-B07 (presidente sem erro, busca, região, evolução por candidato)

Branch `feat/backend-busca-presidente` (não pushada; 2 commits: `test:` vermelho → `feat:`).

## O que fez
**Bugs do presidente (500 → corrigidos).** Causa comum: voto do exterior (`ZZ`) chega com `cd_mun_ibge` nulo.
- `/api/mapa` (grupo ou `sq_candidato`, qualquer nível): exterior sai de `valores`; resposta ganha `votos_fora_do_mapa` (int, 0 se não houver).
- `/api/candidatos/{ano}/{sq}`: exterior entra em `votos_total` e em `votos_por_uf` como `{"uf":"ZZ"}`; município fora do cadastro agora é 503 explícito (`dados_indisponiveis`), nunca `KeyError`/500.
- `/api/candidatos` kpis do grupo: exterior soma no total do grupo.
- `/api/comparativo` sem candidaturas num dos lados (ex.: presidente × MBL 2022) → **422 `sem_par_comparavel`**.
- `/api/mapa/pontos`: `uf` opcional. Sem UF, locais são somados em células lat/lon de 0,1° (centroide ponderado por votos); resposta ganha `grade_graus` (0.1 sem UF, null com UF). `votos_sem_coordenada` vale para o Brasil sem UF.

**Novos recursos.**
- `GET /api/busca?q&ano&cargo&uf&grupo&limite` (limite ≤ 100, padrão 20): nome de urna/civil (sem acento, caixa livre, início de palavra antes de trecho), número de urna (prefixo), número/sigla do partido. Item: ano, sq, nm_urna, nome (civil), numero, cargo, uf (`BR` = presidente), partido, votos, resultado, indicado, `pessoa_id_publico`, `abrangencia`. `%`, `_`, `\` e aspas tratados como texto.
- `abrangencia` `{"tipo":"pais"|"uf","uf":...}` também em `CandidatoResumo` (candidatos, ficha) — **campo novo obrigatório na resposta**; aditivo para o front.
- `GET /api/evolucao/pessoas?q&uf&cargo&limite` (≤ 200, padrão 50): pessoas com candidatura em 2022 e 2026 (join por `pessoa_id`), `de`/`para` resumidos, `mesmo_cargo`, `comparavel` (mesmo cargo e não Senado).
- `GET /api/comparativo`: `comparacao` agora **opcional**; modo seleção com `pessoas=` (lista de `pessoa_id_publico`, hex de 12) e/ou `sq_2022=`/`sq_2026=` (listas, ≤ 50). `comparacao` + seleção → 422 `comparacao_e_selecao`; nenhum → 422 `comparativo_sem_alvo`. Resposta da seleção: `comparacao="selecao"`, `de/para.id="selecao"`.
- `pessoa_id_publico` = `sha256("pub:"+pessoa_id)[:12]` (`api/pessoa.py`; mesma fórmula em SQL e Python, testada). O `pessoa_id` nunca sai.

**Varredura.** `apps/api/scripts/varredura.py` (UA `eleicoes2026-varredura/1.0`): descobre grupos/candidatos pela API e percorre mapa×pontos×candidatos×gastos×comparativo×busca×evolução para cargos × grupos × anos × (sem UF + UFs), todos os majoritários e amostra ≥ 30 por grupo; sai 1 se houver 5xx ou corpo não-JSON. `tests/test_varredura.py` roda a mesma varredura sobre a fixture (> 500 pedidos, só 200/404/422).

## Decisões
- Exterior fora do mapa mas dentro dos totais (ficha/KPIs): o voto é do candidato; só não tem polígono.
- Grade de 0,1° (~11 km) em vez de H3 res 6/7 nos pontos nacionais: evita dependência `h3` na API; o volume é limitado pela paginação existente (`limite` ≤ 50000).
- Busca em SQL (`strip_accents(lower())` sobre a view `candidatos`, sem índice): fixture não mede latência real.
- Fixture: presidente com voto no exterior, nome civil e número, grupo `novo_2026` (partido 30) no `grupos.yaml` de teste (faz o papel do Missão presidente em produção).
- `consulta_cand` agora exige `nr_candidato` e `nm_candidato` na abertura (estão no contrato `CONSULTA_CAND`).

## Pendências
- **Não consegui reproduzir os 500 em produção** (sem `data/processed` local); reproduzi pela causa (exterior sem município) na fixture. Rodar `varredura.py` e o smoke contra produção depois do deploy; o 3,8 s da ficha do Renan Santos não foi medido (provável custo frio da ficha com 5,5 mil municípios) — medir.
- Latência da busca (< 100 ms quente) a confirmar em produção; se passar, materializar a view `candidatos` em memória na abertura.
- Frontend: regenerar tipos do OpenAPI; usar `abrangencia` para enquadrar o mapa, `votos_fora_do_mapa` para aviso, `grade_graus` nos pontos nacionais, `/busca`, `/evolucao/pessoas` e `comparativo?pessoas=`.
- `smoke.py` não cobre presidente/busca ainda (a varredura cobre).

## Verificar
`uv run pytest -q`; `uv run ruff check . && uv run mypy apps/api/src`; `make openapi` sem diff; contra a API viva: `uv run python apps/api/scripts/varredura.py --base http://localhost:8000`. (`make lint` falha no eslint só por falta de `node_modules` neste worktree.)
