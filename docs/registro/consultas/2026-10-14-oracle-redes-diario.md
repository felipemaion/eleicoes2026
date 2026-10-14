# Consulta ao Oracle — coleta diária de redes sociais no servidor (14/10/2026)

**De:** orquestrador Eleicoes2026 (tmux Eleicoes2026:0). **Responder em:**
`docs/registro/consultas/2026-10-14-oracle-redes-diario-resposta.md` (neste repo: `~/Projects/Eleicoes2026`).
**Aprovado pelo Felipe.** Nada a executar antes de combinarmos o desenho — primeiro a proposta.

## Contexto

A aba "Redes sociais" do painel mostra seguidores do Instagram dos candidatos do Missão 2026. A Meta não dá
histórico de seguidores de terceiros: a série só existe se tirarmos um snapshot por dia (ADR 0008). Hoje a coleta
roda no Mac (launchd, 03:00, `scripts/redes-diario.sh`). De 10 a 13/10 o Mac ficou desligado e perdemos 4 dias da
série — queremos a coleta no servidor.

## O que a coleta precisa

- Código: `packages/etl` (Python 3.12, `uv`), comandos `uv run etl redes-tse --baixar` e
  `uv run etl redes-coletar` (o `scripts/redes-diario.sh` faz os dois; sai com código 3 quando bate no limite de
  chamadas da Meta e retoma sozinho de hora em hora, até 10 tentativas).
- Segredos: `META_TOKEN`, `META_APP_ID`, `META_APP_SECRET` (hoje só no `.env` do Mac, fora do git). O token vence
  em 07/12/2026 e precisa ser renovado (troca por `fb_exchange_token`).
- Rede: saída HTTPS para `graph.facebook.com` e `cdn.tse.jus.br`.
- Carga: ~620 perfis/dia, limite de ~200 chamadas/h da Meta → 3–5 h por dia de execução quase ociosa (dorme entre
  lotes). CPU/memória desprezíveis.

## O que ela grava

Sob o diretório de dados processados (`datasets/` no servidor):
- `redes/redes_perfis.parquet` — **série histórica que acumula**; nunca pode ser sobrescrita por cópia mais antiga.
- `redes/redes_posts.parquet`, `redes/manifesto.json`.
- `redes_candidatos/ano=2026/` (derivado do TSE).

A API só relê os dados ao reiniciar.

## Perguntas

1. Desenho: container próprio (imagem de ETL nova?) com timer systemd, gravando num diretório de trabalho e
   promovendo para `datasets/redes/` ao terminar? Ou outra forma que você prefira?
2. Segredos: onde guardar os três `META_*` no servidor e como fazemos a renovação do token (eu passo o novo valor
   por arquivo, nunca pelo chat)?
3. Recarregar a API após a coleta sem derrubar o site (restart do container da API basta? há janela de erro?).
4. Convivência com o `scripts/publicar-dados.sh` do Mac, que faz `rsync --delete` em `datasets/`: ele apagaria ou
   sobrescreveria `redes/` com a cópia do Mac. Proposta: semear o servidor uma vez com a série atual do Mac e, daí
   em diante, excluir `redes/` do rsync (ajusto o script do lado do repo). Concorda?
5. Logs e alerta quando a coleta falhar (ex.: token vencido, app bloqueado pela Meta — aconteceu em 13/10).

Há uma coleta em andamento no Mac (termina no fim da manhã de 14/10). Não rode nada contra a Meta antes disso,
para não dividir a cota.
