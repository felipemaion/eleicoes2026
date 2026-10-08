# Ambiente de agentes

Padrão herdado de `~/Projects/FazendoAcontecerACoisaCerta/docs/ambiente-de-agentes.md`.

## A árvore

```
orquestrador (Opus, tmux Eleicoes2026:0 "orq")   planeja, despacha, revisa, integra, controla contexto
 └── janela "agentes": 4 painéis `claude --agent <papel>` de vida longa, um por papel
      └── subagentes in-process (efêmeros, sem painel; revisores no gate de PR)
```

| Papel | Modelo | Território | Especialidade |
|---|---|---|---|
| `dados` | Sonnet 5.5 | `etl/`, `packages/contratos/`, `data/` | obtenção de dados oficiais, ETL, geo |
| `analise` | Opus 5.5 | `packages/indicadores/`, `docs/metodologia/` | ciência política eleitoral, estatística espacial |
| `backend` | Sonnet 5.5 | `apps/api/` | FastAPI, DuckDB, OpenAPI |
| `frontend` | Sonnet 5.5 | `apps/web/` | D3, MapLibre, dataviz acessível |

Modelo pela dificuldade: Opus para método e decisão; Sonnet para implementação. Definições em
`.claude/agents/<papel>.md` — a mesma serve para painel e para subagente (uma fonte de verdade).

Revisores (subagentes do orquestrador, no gate de PR): `ecc:python-reviewer`,
`ecc:fastapi-reviewer`, `ecc:typescript-reviewer`, `ecc:security-reviewer` (antes do deploy).

## Subir

```bash
make agentes                 # = ./scripts/dev-env.sh (idempotente)
ELEICOES_DRY_RUN=1 ./scripts/dev-env.sh   # confere layout sem pagar o boot dos agentes
```

Cria as janelas `agentes` (4 painéis) e `infra` (monitor do ledger + ctx-watch) na sessão
`Eleicoes2026`. Cada painel nasce na sua **worktree** `.worktrees/<papel>` (branch `agente/<papel>`),
definida na criação do painel (`split-window -c`) — `cd` por send-keys se perde.

## Títulos dos painéis

A borda mostra `papel · modelo · tarefa`, a partir de opções do painel (`@papel`, `@modelo`,
`@tarefa`) — o Claude Code sobrescreve o título nativo. `scripts/agent-title.sh` atualiza a borda
**e** grava o evento no ledger no mesmo comando, para nunca divergirem.

## Despachar tarefa

```bash
./scripts/despachar.sh dados T-D01 "downloader com manifesto"            # mesma sessão
./scripts/despachar.sh dados T-D02 "parsers TSE → Parquet" --limpar      # /clear antes
```

O brief fica em `docs/tarefas/T-xxx.md`; no painel vai só um ponteiro com remetente identificado.
O agente devolve em `docs/registro/handoffs/<papel>-T-xxx.md` e responde `pronto T-xxx`.
O orquestrador lê o handoff (arquivo), não a tela — poupa contexto.

## Gestão de contexto (teto 70%)

- `scripts/ctx-watch.sh` lê `ctx:NN%` da status line de cada painel (`ok` < 60 ≤ `handoff` < 70 ≤ `CRITICO`).
- Ao fim de **cada tarefa**, ou se o painel atingir **60%** no meio dela: o orquestrador pede o
  handoff, envia `/clear` e recondiciona com o próximo brief (`despachar.sh … --limpar`).
- Briefs são autossuficientes (objetivo, arquivos, critério de aceite, links de spec) para que o
  agente recomece limpo sem perder estado: o estado vive no repositório, não na conversa.

## Registro (ledger)

`scripts/ledger.py` lê o `usage` dos transcripts do Claude Code (sem hooks) e os eventos de
`agent-title.sh` em `docs/registro/ledger/AAAA-MM.jsonl`. `make relatorio` gera
`docs/registro/RELATORIO.md` com tokens e custo por tarefa/papel (preços conferidos em 2026-10-07:
Opus 5.5 US$4/20, Sonnet 5.5 US$2/10, Haiku 4.5 US$1/5 por MTok).

## Permissões

Painéis em `acceptEdits` com allowlist em `.claude/settings.json`. Push, criação e merge de PR são negados aos agentes por `--disallowedTools` no `dev-env.sh` (o settings vale também para o orquestrador). Negados a todos:
remoção recursiva, reset destrutivo, `claude -p` e leitura de `.env`/`secrets`.
Publicar e integrar é decisão do orquestrador.

## Comunicação

Toda mensagem entre painéis identifica o remetente: `[Do <papel> Eleicoes2026 (tmux …)]`.
Contato com o agente de infra **Oracle** (`Oracle:0.0`) é exclusivo do orquestrador.
