# Eleicoes2026 — desempenho do Partido Missão (14)

Dashboard público (`eleicoes2026.maionesys.com`) que mede o desempenho dos candidatos do
**Partido Missão (nº 14)** nas eleições gerais de 2026, por município e zona eleitoral, com mapa
de densidade de votos e indicadores de gasto de campanha, e compara com o **grupo MBL de 2022**
(candidatos em outros partidos, lista em `data/reference/`). Feito para expandir a outros
partidos sem mudar código (`config/grupos.yaml`).

> Este arquivo fica **abaixo de 200 linhas**. Detalhe vai para os auxiliares listados abaixo.

## Mapa de leitura

| Preciso de… | Leia |
|---|---|
| Arquitetura, camadas, contratos | `docs/arquitetura.md` |
| Fontes oficiais (URLs, formatos, armadilhas) | `docs/fontes-de-dados.md` |
| Fórmulas e cuidados metodológicos | `docs/metodologia/indicadores.md`, `docs/metodologia/cuidados.md` |
| Quem faz o quê, tmux, contexto, ledger | `docs/ambiente-de-agentes.md` |
| Como trabalhar (TDD, git, PR, revisão) | `docs/fluxo-de-trabalho.md` |
| Decisões e porquês | `docs/adr/` |
| Plano de fases e tarefas | `docs/plano.md`, `docs/tarefas/T-*.md` |
| Deploy no Oracle | `docs/deploy.md` |
| O que já aconteceu | `docs/registro/` (ledger, handoffs, relatório de custo) |

## Repositório

```
etl/                  dados: download TSE/IBGE/BCB → Parquet validado (papel: dados)
packages/contratos/   schemas Parquet + modelos compartilhados (papel: dados)
packages/indicadores/ funções puras de indicadores eleitorais (papel: analise)
apps/api/             FastAPI, DuckDB read-only sobre Parquet (papel: backend)
apps/web/             Vite + TypeScript, D3 v7, MapLibre GL (papel: frontend)
config/grupos.yaml    definição dos grupos comparados (missao_2026, mbl_2022, …)
data/reference/       insumos manuais versionados (lista MBL 2022) — sem CPF
data/raw/ processed/  cache local, fora do git (manifesto com sha256 + DT_GERACAO)
docs/                 toda a documentação; docs/registro/ é o diário do projeto
scripts/              tmux, ledger, despacho de tarefas, ctx-watch
```

## Pilha

- Python 3.12 via `uv` (workspace): polars, duckdb, pydantic v2, FastAPI, pytest, ruff, mypy --strict.
- Web via `pnpm`: TypeScript estrito, D3 v7, MapLibre GL, Vitest, Playwright. Sem framework de UI.
- Mapas: malhas IBGE → PMTiles (tippecanoe); grade H3 para densidade e comparação temporal.
- Deploy: Docker ARM64 no Oracle, Caddy serve estáticos/PMTiles, `/api` vai ao FastAPI.

## Comandos

```bash
make setup        # uv sync + pnpm install + hooks
make test         # todos os testes (py + web)
make lint         # ruff + mypy + eslint + tsc
make etl ANO=2026 # baixa e processa dados oficiais (local; pesado)
make dev          # API (:8000) + web (:5173) com dados processados
make openapi      # regenera docs/api/openapi.json (CI confere diff)
make agentes      # sobe janelas tmux 'agentes' e 'infra'
make relatorio    # docs/registro/RELATORIO.md (tokens e custo)
```

## Regras inegociáveis

### TDD
1. Escreva o teste, **veja falhar** pelo motivo certo, implemente o mínimo, refatore no verde.
2. Commit do teste vermelho antes da implementação quando a tarefa for nova (`test:` → `feat:`).
3. Unidade sem I/O para regra (indicadores, parsers sobre fixture); integração com DuckDB real
   sobre fixtures Parquet — **nunca mock de banco**.
4. Cobertura ≥ 80% por pacote; regra de negócio perto de 100%.
5. Todo indicador tem vetor de teste vindo da spec do analista (`docs/metodologia/indicadores.md`).

### Código
- **SOLID**: routers finos → serviços → `Repository` (Protocol) → DuckDB. Indicadores são funções
  puras polars→polars, sem I/O. Dependências injetadas (FastAPI `Depends`), nunca globais.
- **DRY**: uma fonte de verdade por conceito — schemas em `packages/contratos`, tipos do web
  gerados do OpenAPI, grupos em `config/grupos.yaml`, mapeamentos TSE em um só módulo.
- Nomes de domínio em português (`votos_nominais`, `penetracao`); inglês só para termos técnicos
  consagrados. Funções pequenas, tipos explícitos, sem `Any` silencioso.
- Erros falham alto: nada de `except: pass`, nada de fallback que esconde dado faltante.
- Comentário explica **porquê**, não o quê. Docstring em toda função pública.

### Dados
- Só fontes **oficiais** (TSE, IBGE, BCB). Toda fonte documentada em `docs/fontes-de-dados.md`.
- CSV do TSE: Latin-1, `;`, nulos `#NULO`/`#NE`/`-1`/`-3`, decimal com vírgula. Trate num lugar só.
- Guardar `DT_GERACAO` e sha256 de cada arquivo no manifesto; o dado de 2026 muda diariamente.
- **CPF/título nunca** saem do ETL: viram hash salgado (`pessoa_id`) para ligar 2022↔2026.
- Zona eleitoral **não** se compara entre anos pelo número (rezoneamento). Comparação temporal:
  município (código IBGE) e hexágonos H3. Ver ADR 0003.
- Coroplético só com **taxas**; absolutos em símbolos proporcionais/hexbin.
- Valores de 2022 deflacionados pelo IPCA com mês-base explícito.

### Git
- `main` protegida: só recebe por PR (hook `pre-push` recusa push direto).
- **Uma feature = uma branch** `feat/<papel>-<slug>` (ou `fix/`, `docs/`, `chore/`) = um PR = uma Issue.
- Conventional Commits em português: `feat(api): endpoint de comparativo`.
- **Autor único: Felipe (felipemaion).** Proibido trailer `Co-Authored-By` de IA — o hook
  `commit-msg` recusa. Nada de usuário bot no repositório.
- Agentes **não** fazem `git push` nem `gh pr merge`: o orquestrador revisa e integra.

### Escopo de cada agente
Cada papel tem território exclusivo (ver `.claude/agents/<papel>.md`). Precisa mudar algo fora
do seu território? Pare e peça ao orquestrador — não edite. Contrato entre camadas muda primeiro
no contrato (`packages/contratos` ou OpenAPI), com PR próprio.

## Ciclo de uma tarefa

1. Orquestrador escreve o brief `docs/tarefas/T-xxx.md` (objetivo, arquivos, critério de aceite)
   e abre a Issue.
2. `scripts/despachar.sh <papel> T-xxx "<resumo>"` — título do painel + ledger + ponteiro ao agente.
3. Agente: `git fetch && git rebase origin/main`, cria a branch, TDD, `make lint test` verde.
4. Agente escreve `docs/registro/handoffs/<papel>-T-xxx.md` (o que fez, decisões, pendências,
   como verificar) e responde `pronto T-xxx`.
5. Orquestrador revisa (subagentes revisores), faz push, abre PR, CI verde, merge squash.
6. Contexto do agente > 60% ou tarefa encerrada → `/clear` e próximo brief (`--limpar`).

## Comunicação entre agentes

Toda mensagem a outro painel começa identificando o remetente:
`[Do <papel|orquestrador> Eleicoes2026 (tmux <sessão:painel>)]`. Pergunta longa vai num arquivo;
no painel, só o ponteiro e onde responder. Infra do servidor é com o agente **Oracle**
(tmux `Oracle:0.0`, `~/Projects/OracleServer`) — só o orquestrador fala com ele.

## Economia de tokens

Leia trechos (grep antes de Read), não releia o que acabou de editar, delegue buscas amplas a
subagentes. Lote mecânico usa script ou API direta com Haiku — nunca `claude -p` em laço.
Estime custo (5–10 itens) antes de qualquer lote grande.
