# Registro do projeto

Diário de tudo o que acontece, para auditoria e retomada.

| Arquivo | Conteúdo | Quem escreve |
|---|---|---|
| `decisoes.md` | decisões do dia a dia (data, decisão, por quê, quem) | orquestrador |
| `ledger/AAAA-MM.jsonl` | eventos de tarefa (início/fim/revisão por papel) | `scripts/agent-title.sh` |
| `handoffs/<papel>-T-xxx.md` | entrega de cada tarefa | agente do papel |
| `consultas/` | perguntas e respostas a agentes externos (ex.: Oracle) | orquestrador |
| `RELATORIO.md` | tokens e custo por tarefa/papel | `make relatorio` |

Modelo de handoff:

```markdown
# <papel> · T-xxx — <título>
- Branch / commits:
- O que foi feito:
- Decisões tomadas (e por quê):
- Como verificar (comandos):
- Pendências / perguntas ao orquestrador:
```
