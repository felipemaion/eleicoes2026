"""Estado da última coleta de redes (para o /api/health): quando, resultado e idade em dias."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from api.repositorio.base import Repositorio
from api.servicos.redes_base import em_utc


class ColetaRedes(BaseModel):
    """Última coleta de redes sociais e o resultado da tentativa mais recente."""

    coletado_em: datetime | None = Field(
        description="Última coleta que entrou nos dados (UTC); nula se nunca houve."
    )
    resultado: str | None = Field(
        description="Tentativa mais recente: `ok`, `limite` ou `erro`; nulo sem `status.json`."
    )
    motivo: str | None = Field(description="Motivo informado quando o resultado não é `ok`.")
    dias_desde_ultima_coleta_ok: int | None = Field(
        description="Dias inteiros desde `coletado_em`; nulo se nunca houve coleta bem-sucedida."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "coletado_em": "2026-10-13T09:00:00Z",
                    "resultado": "ok",
                    "motivo": None,
                    "dias_desde_ultima_coleta_ok": 1,
                }
            ]
        }
    )


def montar_coleta_redes(repo: Repositorio, agora: datetime) -> ColetaRedes | None:
    """Combina `status.json` (tentativa mais recente) com a coleta que está nos dados.

    Uma tentativa `erro`/`limite` não conta como coleta boa: os dias valem desde a última coleta
    que de fato gravou snapshots. Sem status e sem dados de redes → `None` (nada a mostrar).
    """
    meta, status = repo.redes_meta(), repo.redes_status()
    if meta is None and status is None:
        return None
    if status is not None and status.resultado == "ok" and status.coletado_em is not None:
        ultima_ok = em_utc(status.coletado_em)
    elif meta is not None:
        ultima_ok = em_utc(meta.coletado_em)
    else:
        ultima_ok = None
    dias = None if ultima_ok is None else max(0, (agora - ultima_ok).days)
    return ColetaRedes(
        coletado_em=ultima_ok,
        resultado=status.resultado if status else None,
        motivo=status.motivo if status else None,
        dias_desde_ultima_coleta_ok=dias,
    )
