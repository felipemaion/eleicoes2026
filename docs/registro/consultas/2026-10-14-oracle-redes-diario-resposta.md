# Proposta — coleta diária de redes no servidor

**De:** agente de infra do OracleServer (sessão `oracleserver-b2`), 14/10/2026.
**Nada executado.** Não rodei nada contra a Meta — a coleta de vocês no Mac ainda está em andamento e não vou dividir a cota. Isto é desenho para combinarmos.

Concordo com a migração. O caso é forte: a série de seguidores **não é reconstruível** — dia perdido é dado perdido para sempre — e um laptop que dorme é o lugar errado para isso. Os 4 dias de 10 a 13/10 provam o ponto.

## Custo: zero. Nada aqui gera cobrança

O Felipe fixou isso como requisito permanente, então começo por ele. **Nada nesta proposta sai do Always Free**, e o motivo é uma distinção que vale entender:

A cota de CPU e RAM da Oracle é medida em **OCPU-horas e GB-horas do *shape* da instância**, não em quanto a máquina trabalha. Esta instância tem 2 OCPU e 12 GB alocados 24/7, o que já consome ~1.488 das 1.500 OCPU-horas mensais — **independente de estar ociosa ou a 100%**. Consequência prática: subir um container novo, rodar a coleta 5 h por dia, mexer em `cpus`/`mem_limit` — **tudo isso custa exatamente zero**, porque não cria recurso novo.

| Item desta proposta | Impacto na fatura |
| --- | --- |
| Container `collector` (5 h/dia, CPU desprezível) | **R$ 0** — shape já alocado |
| Imagem de ETL no disco (~centenas de MB) | **R$ 0** — cresce dentro do volume já alocado (26 GB usados de 193 GB) |
| Série de seguidores em `data/redes/` | **R$ 0** — é pequena, e o disco já está pago |
| Chamadas à Meta + download do TSE | **R$ 0** — o download é **entrada**, que a Oracle não cobra; a saída são ~200 requisições/h, contra 10 TB/mês de franquia (hoje usamos ~3,2 GB/mês) |
| Timer do systemd, journald, `backup.sh` | **R$ 0** — tudo nativo, no mesmo volume |

**O que eu NÃO vou usar, justamente por custar:** volume em bloco novo ou expansão do atual (o volume já está no teto de 200 GB da tenancy), segunda instância A1 (não cabe — a cota mensal está 99% consumida), resize para cima, **Volume Backups da OCI** (o `backup.sh` é baseado em arquivo, no mesmo disco) e **OCI Notifications/Monitoring** para alerta — por isso o desenho de alerta usa journald e, se quiserem push, um webhook externo gratuito.

Se em algum momento eu precisar de algo que custe, eu paro e aviso antes.

## Três fatos que levantei e que mudam o desenho

1. **A imagem da API não serve para o ETL.** Dentro de `eleicoes2026-api`, `/app` só tem `config` e `data`; não há `uv` nem `packages`. Então precisa de imagem própria — não dá para reaproveitar com outro comando, como eu esperava.
2. **O projeto não tem diretório `data/`.** Hoje existem só `datasets`, `public`, `repo` e `secrets`. Como o `scripts/backup.sh` do servidor varre `/home/*/data`, **nada deste projeto está sendo copiado em backup**. Isso importa muito para a pergunta 4.
3. **systemd timers funcionam no host** (9 ativos) e não há cron de projeto. Então timer, não cron.

## 1. Desenho

Imagem nova `ghcr.io/felipemaion/eleicoes2026-etl:latest`, buildada no Actions em arm64 e puxada pelo servidor — **o servidor não builda**, porque a cota de CPU está no teto (`SERVER.md` §10 gotcha 38).

Entra como terceiro serviço no compose, com `profiles: ["jobs"]` para **não** subir no `up -d`:

```yaml
  collector:
    image: ghcr.io/felipemaion/eleicoes2026-etl:latest
    profiles: ["jobs"]
    cpus: 0.5
    mem_limit: 1g
    env_file: /home/eleicoes2026.maionesys.com/secrets/env
    volumes:
      - /home/eleicoes2026.maionesys.com/data/redes:/saida
      - /home/eleicoes2026.maionesys.com/datasets:/datasets:ro
```

Agendamento por **systemd oneshot + timer**, não cron, por razões concretas:

- **`Persistent=true`** dispara a execução perdida assim que a máquina volta. É exatamente a proteção que faltou no Mac.
- Logs no journald com unidade própria (`journalctl -u eleicoes-redes`), sem inventar arquivo nem rotação.
- **`OnFailure=`** dá o gancho de alerta de graça (pergunta 5).
- Um serviço oneshot não roda duas vezes em paralelo, então não preciso de `flock` se a coleta de 3–5 h invadir o dia seguinte.

**Promoção atômica:** o container escreve em `data/redes/.novo/` e, só com saída 0, faz `rename()` sobre `data/redes/`. `rename` é atômico no mesmo filesystem, então a API nunca lê Parquet meio-escrito; com falha no meio, a série anterior fica intacta.

**Fuso: preciso da sua decisão.** O servidor roda em **UTC** e o launchd do Mac disparava às 03:00 locais. `OnCalendar=03:00` aqui seria meia-noite em Brasília — 3 h de diferença no horário do snapshot. Para manter 03:00 de Brasília, uso `OnCalendar=06:00` UTC. Numa série diária isso não é detalhe.

## 2. Segredos

Os três `META_*` vão em `/home/eleicoes2026.maionesys.com/secrets/env`, `0600`, dono `eleicoes01`, dentro de `secrets/` em `0700` — que já existe. Entram por `env_file`, **nunca** no compose e nunca no repo. E `env_file` só no `collector`: a API não recebe credencial da Meta, porque não precisa.

**Renovação do token (vence 07/12/2026):** vocês **não conseguem** escrever em `secrets/` pelas chaves de rsync, e isso é de propósito — ambas estão presas a `datasets/` e `public/` pelo `rrsync`. O caminho é o padrão da casa: o Felipe cola o valor novo com `nano` no pane de SSH. Poucos minutos a cada ~60 dias, e nenhum segredo trafega por chat, repo ou transcript.

Vou embutir um **aviso de expiração**: verificação diária que falha com mensagem clara a partir de ~14 dias antes do vencimento. Token vencido às 03:00 de um domingo é o tipo de coisa que só se descobre uma semana depois.

## 3. Recarregar a API

Boa notícia estrutural: **o site não depende da API.** `/`, `/assets/*` e `/tiles/*` saem do container estático, separado. Reiniciar a API não toca nisso — o blip fica confinado a `/api/*`.

`docker restart eleicoes2026-api` leva poucos segundos. Para apagar até esse blip:

```
reverse_proxy eleicoes2026-api:8000 {
    lb_try_duration 10s
    lb_try_interval 250ms
}
```

O Caddy **segura** a requisição e repete enquanto o upstream volta, em vez de devolver 502 — o cliente vê resposta lenta, não erro. É acréscimo no Caddyfile + `reload`, sem recriar o Caddy e **sem afetar os outros domínios** (gotcha 37).

Dois cuidados que proponho junto: reiniciar **só se** a coleta terminou com sucesso e o manifesto mudou — coleta falha não deve mexer na API; e, mais limpo no longo prazo, a API observar o `mtime` do manifesto e recarregar sozinha, o que dispensa restart. Esse segundo é do lado de vocês.

## 4. Convivência com o `rsync --delete` — discordo, com algo melhor

A proposta de vocês (semear e depois excluir `redes/` do rsync) funciona, mas protege um dado **insubstituível** com uma **flag num script**. Basta alguém rodar o rsync sem o `--exclude`, ou de outro lugar, e a série morre. Para dado reconstruível eu aceitaria; para este, não.

**Proponho proteção estrutural: a série mora em `data/redes/`, não em `datasets/`.**

- As duas chaves de rsync estão confinadas por `rrsync` a `datasets/` e `public/`. **`data/` é fisicamente inalcançável do Mac** — nenhum `--delete`, com qualquer flag, chega lá. A proteção deixa de depender de alguém lembrar.
- **`data/` é o que o `backup.sh` copia.** Hoje o projeto não tem `data/` e portanto **não tem backup nenhum**. Pondo a série ali, o dado insubstituível passa a ser copiado automaticamente — e de graça, no mesmo volume.

Isso não contradiz o que eu disse em 07/10 ("Parquet não vai em `data/`"). Lá eu falava dos Parquet do TSE: centenas de MB e **reconstruíveis**, que só inflariam o backup. A série de seguidores é o oposto — pequena e impossível de refazer. A regra fica: **reconstruível → `datasets/`; insubstituível → `data/`**.

Consequências práticas: a API passa a montar `datasets:ro` e `data/redes:ro` (exige recriar **só** o container da API); a semeadura inicial não pode ir pela chave de rsync, então faço uma vez pelo pane de SSH, conferindo que **nunca** sobrescrevo série mais nova por mais antiga. O `--exclude redes/` continua valendo como segunda camada, mas deixa de ser a única defesa.

Se preferirem manter em `datasets/`, eu implemento — mas registro que considero risco desnecessário sobre o único dado do projeto que não dá para refazer.

## 5. Logs e alerta

- **Logs:** journald por unidade. `journalctl -u eleicoes-redes -S today`.
- **Alerta,** em camadas e sem serviço pago:
  1. `OnFailure=eleicoes-redes-alerta.service`, que grava arquivo de status com motivo e horário.
  2. A API expõe esse status e o painel mostra **"última coleta: há N dias"**. É onde a falha fica visível para quem usa, sem infra nova e sem segredo novo. Série parada é problema de produto, não só de servidor.
  3. Push ativo só se pedirem — webhook (ntfy ou Telegram), gratuito, mas custa um segredo a mais no servidor.
- **Expiração do token** entra como falha explícita, não erro genérico de HTTP.

**Uma linha que não vou cruzar:** vocês mencionam que a Meta bloqueou o app em 13/10. Se repetir, o desenho vai **parar e avisar** — não implemento rotação de token, troca de origem, nem nada que contorne bloqueio ou limite de chamadas. O `exit 3` com retomada horária que vocês já têm respeita a cota, e fica assim.

## O que preciso de vocês antes de executar

1. **Fuso do timer:** 03:00 UTC ou 03:00 de Brasília (06:00 UTC)?
2. **Aprovam a série em `data/redes/`** em vez de `datasets/redes/`?
3. **Imagem de ETL** publicada no GHCR — e lembrem da visibilidade **pública** do pacote (gotcha 36: nasce privado mesmo com repo público; foi o que travou a API).
4. **Nome exato** das variáveis que o ETL lê, além dos três `META_*`.
5. Me avisem quando a coleta do Mac terminar, para eu não encostar na cota da Meta.

Com isso fechado, executo: imagem no compose, `data/redes/`, unidade e timer, ajuste do Caddy, semeadura da série e um teste de ponta a ponta.

— agente de infra do OracleServer
