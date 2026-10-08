# Handoff dados — T-D01 (downloader com manifesto e cache)
Branch `feat/dados-downloader`.

## O que foi feito
- `etl/fontes/catalogo.py`: catálogo declarativo (10 fontes TSE, malha IBGE por UF, IPCA BCB 433);
  `alvos(ano, fontes, uf)` expande URLs (inclui `votacao_secao_{ANO}_{UF}`, 28 UFs com ZZ).
- `etl/download.py`: `Baixador` — pula inalterado via HEAD (ETag, senão Last-Modified); sem
  validadores rebaixa e compara sha256. Escrita `.part` + `replace`; confere Content-Length;
  retry 4x com backoff 1/2/4 s só para rede/5xx; 4xx falha na hora (`DownloadError`).
- `etl/manifesto.py`: JSON ordenado, escrita atômica; `dt_geracao` fica nulo (preenchido em T-D02).
- `etl/cli.py` + script `etl baixar`; código de saída 1 se algum alvo falhar, 2 para argumento inválido.
- Testes com `pytest-httpserver` e `httpx.MockTransport` (sem rede real). Cobertura etl ≈ 98%.

## Decisões
- "Retomar" = refazer do zero (descarta `.part`): TSE CDN não garante Range estável; simples e seguro.
- Exceção chama-se `DownloadError` (ruff N818 exige sufixo Error).
- Download sequencial; paralelismo fica para depois se necessário.
- Sem conferência do `last_modified` real da CDN do TSE (não rodei contra a rede).

## Pendências
- Rodar download real não foi feito (fora de escopo). Comando: `uv run etl baixar --ano 2026` e
  `--ano 2022`. Estimativa: só `votacao_candidato_munzona` ≈ 0,45 GB (2026) + 0,58 GB (2022);
  `votacao_secao` por UF chega a ~0,8 GB (SP), total do ano na casa de vários GB — rode com
  `--fonte` seletivo primeiro. Tempo depende do link (~1 GB/10 min a 15 MB/s).
- Valores de ETag/Last-Modified do CDN real não verificados; se ausentes, cai no fallback sha256.
- `make etl` também chama `etl processar` (T-D02, ainda inexistente).

## Verificar
`make lint test` (verde, 73 testes); `uv run pytest packages/etl -v`.
