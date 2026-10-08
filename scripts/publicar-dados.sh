#!/usr/bin/env bash
# Publica os dados processados localmente no servidor (ADR 0002: ETL roda no Mac, servidor só recebe).
#
#   datasets/  ← Parquet + manifesto.json   (chave ~/.ssh/eleicoes-rsync-datasets, rrsync preso a datasets/)
#   public/tiles/ ← PMTiles + manifesto      (chave ~/.ssh/eleicoes-rsync-public, rrsync preso a public/)
#
# O destino é imposto pelo servidor; por isso os caminhos remotos são relativos à raiz de cada chave.
# --delete é seguro: tudo aqui é reprodutível a partir das fontes oficiais.
#
# Uso: publicar-dados.sh [dir_processed]   (padrão: data/processed)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEM="${1:-$RAIZ/data/processed}"
DESTINO="eleicoes01@167.126.3.134"

# dt_geracao vem de coluna dos próprios Parquet; manifesto.json (situação das contas) é opcional.
[ -d "$ORIGEM/consulta_cand" ] || { echo "sem consulta_cand em $ORIGEM — rode o ETL antes" >&2; exit 1; }
# Defesa extra de privacidade: nenhum CSV transcodificado (com CPF) pode subir.
if find "$ORIGEM" -name '*.csv' -o -name '.etl-*' | grep -q .; then
  echo "recusado: há CSV/temporário do ETL em $ORIGEM" >&2; exit 1
fi

echo "== datasets"
rsync -az --delete --exclude 'tiles/' \
  -e "ssh -i $HOME/.ssh/eleicoes-rsync-datasets -o IdentitiesOnly=yes" \
  "$ORIGEM/" "$DESTINO:"

if [ -d "$ORIGEM/tiles" ]; then
  echo "== tiles"
  # Só os PMTiles e o manifesto: os GeoJSONL intermediários (_geojsonl/) ficam no Mac.
  rsync -az --delete --include 'manifesto.json' --include '*.pmtiles' --exclude '*' \
    -e "ssh -i $HOME/.ssh/eleicoes-rsync-public -o IdentitiesOnly=yes" \
    "$ORIGEM/tiles/" "$DESTINO:tiles/"
fi
echo "publicado. A API relê os dados no próximo deploy/restart (dt_geracao em /api/health)."
