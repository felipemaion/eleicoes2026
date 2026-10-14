# Handoff — dados · T-D09 (imagem de coleta de redes para o servidor)

Branch `feat/dados-imagem-coleta-redes` (sobre `origin/main` 3bc855a). Nada foi enviado ao servidor nem ao GHCR.

## O que foi feito
- `etl redes-servidor` (`packages/etl/src/etl/redes/servidor.py`): lê `redes_candidatos` de `/datasets`,
  **copia a série existente de `/saida` para `/saida/.novo/`**, coleta acrescentando o snapshot do dia e promove
  por `os.replace` (posts → perfis → manifesto) só sem erro. Falha no meio (erro/token/bloqueio) apaga `.novo` e
  deixa a série intacta. `--simular` confere ambiente e entrada sem rede.
- Retomada por limite como no `redes-diario.sh`: até `REDES_TENTATIVAS` (10) com espera `REDES_ESPERA_S` (3600 s).
  Nunca contorna limite ou bloqueio; código 200/190 etc. = erro imediato.
- `/saida/status.json` (escrita atômica) em todo desfecho: `{inicio, fim, resultado: ok|limite|erro, motivo,
  perfis_coletados, coletado_em}` (ISO-8601 UTC) — formato que a API (T-B19) lê.
- Token: vencido/inválido → erro antes de gastar chamadas. A ≤14 dias do vencimento (`REDES_AVISO_DIAS`) a coleta
  roda, promove e sai com **código 4** (+ `motivo` no status e stderr) para o `OnFailure=` do Oracle.
- `packages/etl/Dockerfile` (arm64, uv, usuário uid/gid 10001, `ENTRYPOINT etl`, `CMD redes-servidor`) e
  `.dockerignore` na raiz. Workflow `.github/workflows/imagem-etl.yml` → `ghcr.io/felipemaion/eleicoes2026-etl:latest`
  (+ tag do sha) a cada merge em `packages/etl`, `packages/contratos`, `config/`, `uv.lock`.
- `scripts/publicar-dados.sh` exclui `redes/`; `docs/deploy.md` e `docs/fontes-de-dados.md` atualizados
  (reconstruível → `datasets/`; insubstituível → `data/`).

## Decisões
- **A imagem não baixa o TSE.** `redes_candidatos` (derivado do ZIP do TSE + `consulta_cand`) vem de `/datasets`,
  publicado do Mac com `make publicar-dados`; assim a imagem fica leve (sem GDAL/tippecanoe) e o servidor só fala com a Meta.
  Se o Felipe quiser TSE direto no servidor, é uma tarefa à parte (precisa de `consulta_cand` no volume).
- **Limite persistente promove o parcial** (saída 3, `resultado: limite`): o que foi gravado antes do corte já passou
  pela validação de contrato em `coletar`; a próxima execução continua do cache. Erro nunca promove.
- Promoção é por arquivo (`/saida` é ponto de montagem e guarda `status.json`; não dá `rename` do diretório).
  Mesmo filesystem ⇒ cada troca é atômica; o manifesto, que a API usa como versão, vai por último.

## Variáveis de ambiente (lista exata)
| Variável | Padrão | Uso |
|---|---|---|
| `META_TOKEN` | — (obrigatória) | token Graph API |
| `META_APP_ID`, `META_APP_SECRET` | — (sem elas: aviso, validade não conferida) | `debug_token` / expiração |
| `ELEICOES_DIR_DATASETS` | `/datasets` | entrada `redes_candidatos/ano=AAAA/` (ro) |
| `ELEICOES_DIR_SAIDA` | `/saida` | série + `status.json` (rw, uid 10001) |
| `REDES_ANO` | 2026 | ano de `redes_candidatos` |
| `REDES_TENTATIVAS` | 10 | tentativas ao bater no limite |
| `REDES_ESPERA_S` | 3600 | espera entre tentativas |
| `REDES_AVISO_DIAS` | 14 | dias antes do vencimento para o código 4 |

Códigos de saída: 0 ok · 1 erro · 3 limite persistente · 4 ok + token perto de vencer.
O dono de `data/redes` no host deve ser uid **10001** (ou a pasta gravável por ele). `.novo/` só vive durante a execução.

## Para o orquestrador / Oracle
- **O pacote GHCR `eleicoes2026-etl` nasce PRIVADO**: tornar público após o 1º push na main (Package settings).
- Execução: `docker run --rm --env-file <secrets/env> -v .../data/redes:/saida -v .../datasets:/datasets:ro ghcr.io/felipemaion/eleicoes2026-etl:latest`
  (cpus 0.5 / mem 1g bastam). Checagem sem rede: acrescentar o argumento `redes-servidor --simular`.
- Semear `/saida` com a série atual do Mac (`data/processed/redes/*`) por SSH, uma vez, sem sobrescrever série mais nova.

## Como verificar
`uv run pytest packages/etl/tests/test_redes_servidor.py` (11 testes: acréscimo sem perder snapshots, falha preserva
a série, limite retoma/persiste, token vencido/aviso/15 dias, status.json, `--simular`) · `make lint test` (py).
`docker build` arm64 local: ok (645 MB, uid 10001); `docker run … redes-servidor --help` e `--simular` ok.
**Ressalva:** neste Mac o Docker não alcançava `ghcr.io`/Docker Hub-frontend (travava em `load metadata`), então o build
local usou `pip install uv==0.8.22` no lugar do `COPY --from=ghcr.io/astral-sh/uv` e sem a linha `# syntax` — o
Dockerfile versionado é o mesmo da imagem da API nesses pontos e deve buildar no Actions; confirmar no 1º run do workflow.
Pendências: nenhuma de código.
