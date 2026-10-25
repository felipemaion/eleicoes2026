# Handoff dados — T-D14 (certifi sem a raiz emSign ECC G3)

**Branch:** `fix/dados-certifi` · **Issue:** #118

## O que foi feito
- `uv lock --upgrade-package certifi`: **2026.7.22 → 2026.10.23**. Só o certifi mudou no `uv.lock` (3 linhas).
- Teste `packages/etl/tests/test_certifi.py` (unidade, sem rede): falha se `certifi.contents()` contiver
  "emSign ECC Root CA - G3". Visto vermelho com 2026.7.22 e verde com 2026.10.23 (commits `test:` → `fix:`).
- `make lint test` do ETL verde.

## Dockerfile (`packages/etl/Dockerfile`)
- Instala com `uv sync --frozen --no-dev … --package etl`: o certifi da imagem **é o do lock**. Não há pip solto.
- O código não sobrescreve TLS (sem `verify=`, `SSL_CERT_FILE` ou `REQUESTS_CA_BUNDLE`): o httpx usa o certifi.
- A imagem `python:3.12-slim-bookworm` traz também o bundle do sistema (`/etc/ssl/certs`), mas nenhum código do
  ETL o usa. Se algum dia for usado (ex.: curl no container), ele segue a versão do Debian, fora deste controle.

## Publicação da imagem
O workflow `imagem-etl` roda em push na `main` quando mudam `uv.lock` ou `packages/etl/**` (este PR muda os dois),
então a imagem `ghcr.io/felipemaion/eleicoes2026-etl:latest` é reconstruída ao integrar. Depois, o Oracle faz pull.

## Como o Oracle confere (dentro do container)
```bash
docker run --rm --entrypoint python ghcr.io/felipemaion/eleicoes2026-etl:latest \
  -c "import certifi; print(certifi.__version__); print('emSign ECC Root CA - G3' in certifi.contents())"
# esperado: 2026.10.23 e False
docker run --rm --entrypoint sh ghcr.io/felipemaion/eleicoes2026-etl:latest \
  -c 'grep -c "emSign ECC Root CA - G3" "$(python -c "import certifi;print(certifi.where())")"'
# esperado: 0
```

## Pendências
Nenhuma. Pull da imagem nova no servidor fica com o Oracle após o merge.
