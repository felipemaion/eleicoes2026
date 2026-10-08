# Logs do 500 — e as duas hipóteses caem

Não reiniciei nem alterei nada, como pedido. Tudo abaixo é leitura.

**Resumo:** não é `temp_directory` e não é o container. O limite de memória que o DuckDB está aplicando é **400 MB**, não os 1200 MB que vocês acham que configuraram — e nenhuma variável de memória chega ao processo.

## O erro

```
_duckdb.OutOfMemoryException: Out of Memory Error: failed to offload data block
of size 96.0 KiB (381.4 MiB/381.4 MiB used).
* Increasing the memory limit (SET memory_limit='...GB')
```

Repete idêntico nas três ocorrências do log. O traceback é todo de middleware do Starlette (`errors.py`, `_exception_handler.py`) — a exceção nasce no DuckDB e sobe sem tratamento, virando 500.

**O número é a pista.** 381,4 MiB não é um valor arbitrário: `400.000.000 bytes ÷ 2²⁰ = 381,47 MiB`. O DuckDB reporta em MiB o que foi configurado em MB decimais. **O `memory_limit` em vigor é 400MB.**

Como não há nenhuma variável de memória no ambiente do container (lista completa abaixo), o mais provável é que a aplicação esteja caindo num **default de 400MB no próprio código**, e que os 1200 MB estejam sendo definidos num caminho que não é executado em produção — ou lidos de uma variável que ninguém passa.

Vale confirmar do lado de vocês logando no startup:

```sql
SELECT current_setting('memory_limit'), current_setting('temp_directory'), current_setting('threads');
```

Isso encerra a dúvida em uma linha de log, em vez de inferência.

## Hipótese 1 — `temp_directory`: DESCARTADA

```
uid=10001(app) gid=10001(app)
drwxrwxrwt 1 root root /tmp
drwxr-xr-x 2 app  app  /tmp/duck
→ GRAVAVEL   (criei um arquivo de teste e removi)
```

O diretório existe e o usuário do container escreve nele. O "failed to offload" **não** é falta de lugar para derramar: é o DuckDB batendo no teto de 400MB e recusando até um bloco de 96 KiB.

## Hipótese 2 — memória do container: DESCARTADA

```
OOMKilled=false   RestartCount=0   ExitCode=0
Up 4 minutes (healthy)
memory.max (cgroup) = 2147483648  → 2 GiB
```

```
CONTAINER ID   NAME               CPU %    MEM USAGE / LIMIT   MEM %    NET I/O       BLOCK I/O
23ac1adefb0b   eleicoes2026-api   86.89%   1.385GiB / 2GiB     69.25%   124kB/2.4MB   3.31MB/2.59GB
```

O cgroup nunca matou o processo. **Sobram ~600 MiB** no container no momento da medição. O limite que falhou é interno ao DuckDB.

## Ambiente, completo

```
ELEICOES_ARQUIVO_GRUPOS=/app/config/grupos.yaml
ELEICOES_CORS_ORIGINS=https://eleicoes2026.maionesys.com
ELEICOES_DIR_DADOS=/datasets
ELEICOES_DUCKDB_THREADS=2
ELEICOES_RAIZ_REPOSITORIO=/app
ELEICOES_THREADS=2
```

Duas observações sobre isto:

- **Não há variável de memória nenhuma.** E é em parte responsabilidade minha: na consulta do compose vocês me passaram três variáveis (`DIR_DADOS`, `DUCKDB_THREADS`, `CORS_ORIGINS`) e eu setei exatamente essas três. Se a aplicação espera algo como `ELEICOES_DUCKDB_MEMORIA`, **me diga o nome exato e eu acrescento** — o compose é root, vocês não conseguem editar.
- `ELEICOES_THREADS=2` aparece sem eu ter setado, então **a imagem assa defaults próprios**. Vale verificar se o `memory_limit` de 400MB também vem de lá — seria o caminho mais curto para a explicação.

## Cuidado antes de simplesmente subir o limite

Subir o DuckDB para 1200MB **sem subir o do container** tende a trocar um problema por um pior: hoje são 1,385 GiB residentes com o DuckDB preso em 400MB, ou seja, cerca de 1 GiB é Python, buffers e cache de página contados no cgroup. Dando 800 MB a mais ao DuckDB, o total passa de 2 GiB e aí o cgroup **mata** o container — você troca 500 pontual por 502 e restart, que é mais difícil de diagnosticar.

Então, se quiserem 1200MB, o certo é fazer as duas coisas juntas. Do meu lado há folga confortável: o host usa 1,6 GB de 12 GB, então posso levar o `mem_limit` para 3g sem risco e sem efeito em cobrança (a cota da Oracle é sobre o shape da instância, não sobre limites de container).

Também vale olhar a consulta em si antes de dar mais memória: 87% de CPU e **2,59 GB lidos do disco** para um único endpoint de candidato sugerem varredura de Parquet sem *pushdown* de filtro. Se o 500 some com mais memória mas a consulta continuar lendo 2,6 GB, o endpoint vai ficar lento e os 2 OCPU são compartilhados com outros quatro serviços.

## O que preciso de vocês para agir

Como foi pedido só consulta, **não mudei nada**. Me autorizem o que quiserem:

1. Acrescentar a variável de memória ao compose — **preciso do nome exato**.
2. Subir `mem_limit` de 2g para 3g (requer recriar só este container; **não afeta outros domínios**).

Qualquer um dos dois é rápido. Recomendo os dois juntos, nessa ordem, e só depois reavaliar a consulta.

— agente de infra do OracleServer 
