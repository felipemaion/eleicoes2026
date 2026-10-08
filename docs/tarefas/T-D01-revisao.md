# T-D01 — correções da revisão (PR #24)
Corrigir no branch `feat/dados-downloader` (TDD: teste primeiro):
1. [BLOQUEANTE] `download.py:88-89`: soma de bytes decodificados comparada com Content-Length (bytes
   no fio). Com gzip (IBGE/BCB) sempre parece truncado. Comparar com `resp.num_bytes_downloaded` ou
   usar `iter_raw` + `Accept-Encoding: identity` para ZIPs. Teste com resposta gzip.
2. [ALTA] HEAD com 4xx (403/405) aborta alvo em cache: em `_inalterado`, `DownloadError` → `False`
   (cai no GET). Em `_com_retry`, 408/429 são repetíveis respeitando `Retry-After`.
3. [ALTA] `OSError` (disco cheio), `httpx.TooManyRedirects`, `httpx.DecodingError` escapam e matam o
   lote: converter `OSError`/`httpx.HTTPError` em `DownloadError`; o laço segue e sai com código 1.
4. Curtas: `fsync` do `.part` antes do `replace`; opção `--verificar` que recalcula sha256 local;
   `test_sem_validadores_decide_por_sha256` deve afirmar que houve GET e que o hash decidiu.
Depois: `make lint test`, commit, seção "Revisão" no handoff.
