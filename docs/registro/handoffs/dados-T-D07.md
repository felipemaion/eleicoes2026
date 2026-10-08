# Handoff dados — T-D07 (fotos oficiais dos candidatos)

Branch `feat/dados-fotos`. Sem push (orquestrador integra).

## O que foi feito
- `etl.fontes.catalogo`: fonte `fotos` (por UF; `CDN_TSE_FOTOS`; `UF_SEM_FOTOS` pula ZZ em 2022 e 2026).
- `etl.fotos`: `selecionar_sqs`, `processar_fotos` (ZIP → WebP 160×200 q70, manifesto, idempotente por
  `sha256_origem`, falha alto em ZIP/imagem inválidos). CLI: `etl fotos --ano A [--baixar] [--uf UF]`.
- Dependência nova: `pillow` (pacote `etl`; `uv.lock` atualizado).
- Testes `packages/etl/tests/test_fotos.py` (6) com ZIP sintético gerado no teste (sem binário no git).
- `docs/fontes-de-dados.md`: seção "Fotos dos candidatos".

## Números reais (rodado local em 2026-10-08)
| ano | fotos | bytes WebP | sem foto na seleção |
|---|---|---|---|
| 2026 | 20.301 | 50,7 MB | 1 |
| 2022 | 28.695 | 75,0 MB | 25 (quase todos INAPTOS; 13 em MS) |
| **total** | **48.996** | **125,8 MB** (< meta de 150 MB) | |

`du` mostra 213 MB por causa de blocos de 4 KB; `manifesto.json` = 13,9 MB. Seleção: cargos 1–8 dos
dois anos + todo o partido 14 em 2026 (inclui suplentes). Os 18 candidatos da lista MBL (2022 e 2026)
têm foto: 18/18 nos dois anos. Média ≈ 2,6 KB/foto. ETL: ~1 min (2026) e ~2 min (2022, com download).

## Decisões
- ZZ: 404 também em 2026 → ausente do catálogo de fotos (somente para essa fonte).
- Recorte `ImageOps.fit` com âncora (0,5; 0,25) — rosto no terço superior; conferido visualmente.
- `manifesto.json` guarda também `sha256_origem` (detecta troca de foto pelo TSE com o mesmo nome).

## Diff proposto para `scripts/publicar-dados.sh` (território do orquestrador)
O rsync de datasets usa `--delete` e só exclui `tiles/`: **sem excluir `fotos/` ele subiria as fotos para
`datasets/` (e o `--delete` do destino as apagaria)**. Proposta:
```diff
-"$RSYNC" -az --delete --exclude 'tiles/' \
+"$RSYNC" -az --delete --exclude 'tiles/' --exclude 'fotos/' \
   -e "ssh -i $HOME/.ssh/eleicoes-rsync-datasets -o IdentitiesOnly=yes" \
   "$ORIGEM/" "$DESTINO:"
@@
+if [ -d "$ORIGEM/fotos" ]; then
+  echo "== fotos"
+  # Só WebP e manifesto → public/fotos/ (Caddy serve em /fotos/<ano>/<sq>.webp).
+  "$RSYNC" -az --delete --include '*/' --include 'manifesto.json' --include '*.webp' --exclude '*' \
+    -e "ssh -i $HOME/.ssh/eleicoes-rsync-public -o IdentitiesOnly=yes" \
+    "$ORIGEM/fotos/" "$DESTINO:fotos/"
+fi
```
Pendência Oracle (via orquestrador): confirmar que o Caddy serve `public/fotos/` em `/fotos/*` com
`Cache-Control` longo (nomes por `sq`, imutáveis por candidatura; trocas de foto são raras).

## Como verificar
```bash
.venv/bin/pytest packages/etl/tests/test_fotos.py -q
.venv/bin/etl fotos --ano 2026 --baixar && .venv/bin/etl fotos --ano 2022 --baixar
ls data/processed/fotos/2026 | wc -l   # 20301
```
Pendências: nenhuma de dados. Frontend deve tratar 404 (candidato sem foto) com avatar neutro.
