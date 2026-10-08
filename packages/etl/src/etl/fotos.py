"""Fotos oficiais dos candidatos: ZIPs do TSE (JPEG) → WebP 160×200 + manifesto.

Fonte: ``cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoesAAAA/fotos/foto_candAAAA_<UF>_div.zip``
(ver ``docs/fontes-de-dados.md``). O nome do arquivo no ZIP é ``F<UF><SQ_CANDIDATO>_div.jpg|jpeg``;
a chave de ligação com ``consulta_cand`` é o ``sq_candidato``. Nada aqui lê CPF/título.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import polars as pl
from PIL import Image, ImageOps, UnidentifiedImageError

LARGURA, ALTURA = 160, 200
QUALIDADE_WEBP = 70
# Rostos ficam no terço superior do retrato: o corte de proporção preserva o topo.
CENTRO_CORTE = (0.5, 0.25)
CARGOS_FOTOGRAFADOS = tuple(range(1, 9))  # presidente … deputado distrital (sem suplentes)
NR_PARTIDO_MISSAO = 14  # grupos missao_2026/mbl_2026 (config/grupos.yaml)
_NOME = re.compile(r"^F[A-Z]{2}(?P<sq>\d+)_div\.jpe?g$", re.IGNORECASE)


class ErroFotos(RuntimeError):  # noqa: N818 - nome de domínio
    """Foto ou ZIP inválido: falha alto, nada de pular em silêncio."""


def selecionar_sqs(raiz_processed: Path, ano: int) -> set[str]:
    """``sq_candidato`` a fotografar: cargos 1–8 e, em 2026, todo candidato do partido 14."""
    arquivos = sorted((raiz_processed / "consulta_cand" / f"ano={ano}").glob("*.parquet"))
    if not arquivos:
        raise ErroFotos(f"sem consulta_cand de {ano} em {raiz_processed} — rode o ETL antes")
    criterio = pl.col("cd_cargo").is_in(CARGOS_FOTOGRAFADOS)
    if ano == 2026:
        criterio = criterio | (pl.col("nr_partido") == NR_PARTIDO_MISSAO)
    df = (
        pl.scan_parquet(arquivos)
        .filter(criterio)
        .select(pl.col("sq_candidato").cast(pl.String))
        .collect()
    )
    return set(df["sq_candidato"].to_list())


def _para_webp(jpeg: bytes) -> bytes:
    with Image.open(io.BytesIO(jpeg)) as aberta:
        rgb = ImageOps.exif_transpose(aberta).convert("RGB")
        recorte = ImageOps.fit(
            rgb, (LARGURA, ALTURA), Image.Resampling.LANCZOS, centering=CENTRO_CORTE
        )
        buf = io.BytesIO()
        recorte.save(buf, "WEBP", quality=QUALIDADE_WEBP, method=6)
    return buf.getvalue()


def _carregar(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        return {"fotos": {}}
    return json.loads(caminho.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def processar_fotos(ano: int, zips: list[Path], saida: Path, *, sqs: set[str]) -> dict[str, int]:
    """Converte as fotos de ``sqs`` encontradas em ``zips`` para ``saida/<ano>/<sq>.webp``.

    Idempotente: reaproveita o WebP quando o sha256 do JPEG de origem não mudou.
    O manifesto (``saida/manifesto.json``) acumula entre execuções (uma por UF ou todas).
    """
    caminho_manifesto = saida / "manifesto.json"
    manifesto = _carregar(caminho_manifesto)
    fotos: dict[str, dict[str, str]] = manifesto["fotos"]
    (saida / str(ano)).mkdir(parents=True, exist_ok=True)
    achados: set[str] = set()
    stats = {"extraidas": 0, "reaproveitadas": 0, "fora_da_selecao": 0, "sem_foto": 0, "bytes": 0}
    for caminho in zips:
        try:
            z = zipfile.ZipFile(caminho)
        except (zipfile.BadZipFile, OSError) as e:
            raise ErroFotos(f"{caminho.name}: ZIP ilegível ({e})") from e
        with z:
            for info in z.infolist():
                m = _NOME.match(info.filename)
                if m is None:
                    continue  # leiame.pdf e afins
                sq = m["sq"]
                if sq not in sqs:
                    stats["fora_da_selecao"] += 1
                    continue
                achados.add(sq)
                bruto = z.read(info)
                sha_origem = hashlib.sha256(bruto).hexdigest()
                chave = f"{ano}/{sq}"
                destino = saida / str(ano) / f"{sq}.webp"
                atual = fotos.get(chave)
                if atual and atual.get("sha256_origem") == sha_origem and destino.exists():
                    stats["reaproveitadas"] += 1
                    stats["bytes"] += destino.stat().st_size
                    continue
                try:
                    webp = _para_webp(bruto)
                except (UnidentifiedImageError, OSError, ValueError) as e:
                    raise ErroFotos(f"{caminho.name}:{info.filename}: imagem ilegível ({e})") from e
                parcial = destino.with_name(destino.name + ".part")
                parcial.write_bytes(webp)
                parcial.replace(destino)
                fotos[chave] = {
                    "arquivo": f"{ano}/{sq}.webp",
                    "origem": f"{caminho.name}:{info.filename}",
                    "sha256": hashlib.sha256(webp).hexdigest(),
                    "sha256_origem": sha_origem,
                }
                stats["extraidas"] += 1
                stats["bytes"] += len(webp)
    stats["sem_foto"] = len(sqs - achados)
    manifesto["fotos"] = dict(sorted(fotos.items()))
    parcial_m = caminho_manifesto.with_name("manifesto.json.part")
    parcial_m.write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")
    parcial_m.replace(caminho_manifesto)
    return stats
