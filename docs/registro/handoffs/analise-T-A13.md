# Handoff — analise · T-A13 · conta analisada fixa, sem fallback

- **Branch:** `fix/analise-conta-analisada-fixa` (a partir de `origin/main` 30c2757) · **Issue:** #122
- **Commits:** `e8832c3` test (vermelho: o vetor dava `jaguar` no lugar de `renan`) → `15aa836` fix → este handoff.
- `make lint test` verde (972 py + 426 web); `indicadores.redes` com 100% de cobertura.

## O que mudou
- **Regra nova** (spec §9.0, âncora `#conta-analisada`): conta analisada = a de **mais seguidores em qualquer
  snapshot válido da série** (máximo histórico; empate: `username`). Falha de coleta nunca troca a conta; ela só
  muda se outra superar o máximo histórico.
- `redes.conta_analisada(perfis)` (nova, pública): uma linha por `sq_candidato` com `username, status,
  status_ultima_coleta, seguidores, seguindo, ultima_coleta_ok, conta_indisponivel_desde, desatualizado`.
- `redes.indicadores_candidato` usa `conta_analisada`; números vêm do **último snapshot válido** da conta.
- `redes.metricas_janelas`: seguidores e fim das janelas abertas (`pos_eleicao`, `total`) = último snapshot
  **válido** da conta (antes, conta com último snapshot falho sumia das janelas).
- `redes.aplicar_renomeacoes(df, renomeacoes | None)` (nova): ponto de extensão para a T-D15 — mapa
  `username_tse → username_atual` aplicado a perfis **e** posts antes dos indicadores; `None` = sem efeito;
  `username_tse` repetido ou mapa encadeado falha alto. Nada depende dele.
- Vetor `seguidores_votos.json` v2: caso `conta_analisada_fixa_sem_fallback` (principal falha no fim → segue
  analisada com aviso; lateral cresce sem passar o máximo → não troca; queda da principal abaixo da lateral
  atual → não troca; nunca teve dado → `tem_dados=false`; empate; falhou e voltou → não desatualizada).
- `publico/textos.json`: aviso `redes_conta_indisponivel` (atenção) na tela `redes`, placeholders globais
  `{conta_indisponivel_desde}` e `{ultima_coleta_ok}`; denominador de `seguidores_votos` reescrito.

## Decisões
- **Nenhum indicador vira nulo quando desatualizado**: numerador e denominador cobrem o mesmo período (janela
  termina na última coleta válida; posts só são lidos quando o perfil é encontrado). Anular a variação de ritmo
  esconderia semanas de dado real; a proteção é a data + aviso obrigatório. Está justificado na spec.
- **`status` não ganhou o valor `sem_dados`**: o brief diz "como hoje", e hoje a ausência total de dado é
  `tem_dados = false` com o `status` cru (`nao_encontrado`/`nao_comercial`), que a tela usa para "só link".
  Mantive assim para não quebrar o contrato. Se o orquestrador quiser o literal `sem_dados`, é uma linha.
- `status` = status do último snapshot **válido** (fica `ok` para a conta desatualizada, preservando a leitura
  "status ≠ ok ⇒ sem métrica"); o status cru da coleta mais recente vai em `status_ultima_coleta`.
- Sem ADR: é correção de regra dentro da §9.0, não decisão de arquitetura.

## Contrato sugerido para o backend
No resumo por candidato (hoje alimentado por `indicadores_candidato`), expor:

| campo | tipo | significado |
|---|---|---|
| `status_ultima_coleta` | string \| null | status cru da coleta mais recente da conta analisada |
| `ultima_coleta_ok` | datetime UTC \| null | coleta do snapshot usado nos números |
| `conta_indisponivel_desde` | datetime UTC \| null | primeira coleta falha depois de `ultima_coleta_ok` |
| `desatualizado` | bool | `conta_indisponivel_desde` não nulo (falso para `sem_rede` e sem dados) |

- **Atenção no backend:** `redes_correlacoes.py:281` monta `ultimo_status` pelo último snapshot de cada conta
  e `redes_base.py` guarda `ultimo={(sq, username): snapshot}` pelo último (inclusive falho). Para a conta
  analisada desatualizada isso devolve `nao_encontrado`/seguidores nulos — usar os campos do resumo (ou
  `ind.conta_analisada`) em vez do último snapshot cru. Quando a T-D15 entregar o mapa, chamar
  `ind.aplicar_renomeacoes` em perfis e posts antes de `indicadores_candidato`/`metricas_janelas`.
- **Frontend:** com `desatualizado = true`, exibir o aviso `redes_conta_indisponivel` preenchendo os
  placeholders com as datas (dd/mm/aaaa, Brasília).

## Como verificar
```bash
uv run pytest packages/indicadores -q -k "seguidores_votos or renomea or metricas_janelas_usa"
make lint test
```

## Pendências
- Backend expor os campos e parar de ler o último snapshot cru (acima); frontend exibir o aviso.
- T-D15 (dados): mapa de renomeação e correção da coleta do `@renansantosmbl`.
