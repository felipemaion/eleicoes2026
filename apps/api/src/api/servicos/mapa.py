"""Casos de uso /mapa e /mapa/pontos: valores por território para o coroplético e a densidade."""

import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Indicador, Nivel
from api.erros import parametro_invalido
from api.repositorio.base import Repositorio
from api.servicos import adaptador_indicadores as ind
from api.servicos.escopo import selecionar_alvo
from api.servicos.grupos import Catalogo

_UNIDADE = {Indicador.PENETRACAO: "‰", Indicador.PCT_VALIDOS: "%", Indicador.VOTOS: "votos"}
_DENOMINADOR = {
    Indicador.PENETRACAO: "aptos",
    Indicador.PCT_VALIDOS: "votos_validos",
    Indicador.VOTOS: None,
}


class Detalhe(BaseModel):
    """Numerador e denominadores de um território."""

    votos: int
    aptos: int
    validos: int | None = Field(description="null no H3: não há 'válidos' por célula (§2.2).")
    taxa: float | None = Field(description="Valor do indicador; null = sem dado (denominador 0).")


class EscalaSugerida(BaseModel):
    """Sugestão de classes para a legenda (spec §8.2); o front decide a cor final."""

    tipo: str = Field(description="`sequencial` (taxas) ou `simbolo_proporcional` (absolutos).")
    paleta: str
    quebras: list[float] = Field(
        description="Cortes internos (quintis dos valores desta resposta)."
    )


class Mapa(BaseModel):
    """Corpo de GET /mapa. Chaves: IBGE (município), `IBGE-zona`, ou índice H3."""

    ano: int
    nivel: str
    indicador: str
    valores: dict[str, float | None]
    detalhes: dict[str, Detalhe]
    escala_sugerida: EscalaSugerida
    unidade: str
    denominador: str | None
    n_candidaturas: int
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ano": 2026,
                    "nivel": "municipio",
                    "indicador": "penetracao",
                    "valores": {"3550308": 73.33, "3509502": 20.0},
                    "detalhes": {
                        "3550308": {"votos": 1100, "aptos": 15000, "validos": 10500, "taxa": 73.33}
                    },
                    "escala_sugerida": {
                        "tipo": "sequencial",
                        "paleta": "viridis",
                        "quebras": [20.0, 40.0, 60.0, 70.0],
                    },
                    "unidade": "‰",
                    "denominador": "aptos",
                    "n_candidaturas": 2,
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


def _escala(indicador: Indicador, valores: Sequence[float]) -> EscalaSugerida:
    if indicador is Indicador.VOTOS:
        return EscalaSugerida(tipo="simbolo_proporcional", paleta="um_matiz", quebras=[])
    quebras = (
        [round(q, 2) for q in statistics.quantiles(valores, n=5, method="inclusive")]
        if len(valores) >= 2
        else []
    )
    return EscalaSugerida(tipo="sequencial", paleta="viridis", quebras=quebras)


def montar_mapa(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    nivel: Nivel,
    indicador: Indicador,
    grupo_id: str | None,
    sq_candidato: int | None,
) -> Mapa:
    """Indicador por território; com aptos e sem voto = 0, sem aptos = null (nunca inf)."""
    if nivel is not Nivel.MUNICIPIO and uf is None:
        raise parametro_invalido("uf_obrigatoria", f"nivel={nivel.value} exige 'uf'")
    if nivel is Nivel.H3 and indicador is Indicador.PCT_VALIDOS:
        raise parametro_invalido(
            "indicador_indisponivel", "pct_validos não existe no H3; use penetracao ou votos"
        )
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    sqs = [c.sq_candidato for c in alvo]
    detalhes: dict[str, Detalhe] = {}
    if nivel is Nivel.H3:
        assert uf is not None  # noqa: S101 - exigido acima
        for cel in repo.votos_h3(ano, sqs, uf=uf):
            detalhes[cel.h3] = _detalhe(indicador, cel.votos, cel.aptos, None)
    else:
        por_zona = nivel is Nivel.ZONA
        votos = {
            (v.cd_mun_ibge, v.nr_zona): v.votos
            for v in repo.votos_territorio(ano, sqs, por_zona=por_zona, uf=uf)
        }
        base = repo.base_eleitoral(ano, cargo, por_zona=por_zona, uf=uf)
        vistos = set()
        for b in base:
            vistos.add((b.cd_mun_ibge, b.nr_zona))
            detalhes[_chave(b.cd_mun_ibge, b.nr_zona)] = _detalhe(
                indicador, votos.get((b.cd_mun_ibge, b.nr_zona), 0), b.aptos, b.validos
            )
        for (mun, zona), n in votos.items():  # voto sem base: aparece como "sem dado", não some
            if (mun, zona) not in vistos:
                detalhes[_chave(mun, zona)] = _detalhe(indicador, n, 0, 0)
    valores = {k: d.taxa for k, d in detalhes.items()}
    return Mapa(
        ano=ano,
        nivel=nivel.value,
        indicador=indicador.value,
        valores=valores,
        detalhes=detalhes,
        escala_sugerida=_escala(indicador, [v for v in valores.values() if v is not None]),
        unidade=_UNIDADE[indicador],
        denominador=_DENOMINADOR[indicador],
        n_candidaturas=len(alvo),
        dt_geracao=repo.dt_geracao(),
    )


def _chave(cd_mun_ibge: int, nr_zona: int | None) -> str:
    return str(cd_mun_ibge) if nr_zona is None else f"{cd_mun_ibge}-{nr_zona}"


def _detalhe(indicador: Indicador, votos: int, aptos: int, validos: int | None) -> Detalhe:
    if indicador is Indicador.VOTOS:
        taxa: float | None = float(votos)
    elif indicador is Indicador.PENETRACAO:
        taxa = ind.penetracao(votos, aptos)
    else:
        taxa = ind.pct_validos(votos, validos or 0)
    return Detalhe(votos=votos, aptos=aptos, validos=validos, taxa=taxa)


class Ponto(BaseModel):
    """Local de votação."""

    lat: float
    lon: float
    votos: int


class Pontos(BaseModel):
    """Corpo de GET /mapa/pontos (densidade de votos por local)."""

    ano: int
    total: int = Field(description="Locais com voto no recorte.")
    limite: int
    offset: int
    truncado: bool = Field(description="Há mais páginas além desta.")
    pontos: list[Ponto]
    dt_geracao: str


def montar_pontos(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str,
    grupo_id: str | None,
    sq_candidato: int | None,
    limite: int,
    offset: int,
) -> Pontos:
    """Locais de votação com voto, mais votados primeiro, paginados."""
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    total, linhas = repo.pontos(
        ano, [c.sq_candidato for c in alvo], uf=uf, limite=limite, offset=offset
    )
    return Pontos(
        ano=ano,
        total=total,
        limite=limite,
        offset=offset,
        truncado=offset + len(linhas) < total,
        pontos=[Ponto(lat=p.lat, lon=p.lon, votos=p.votos) for p in linhas],
        dt_geracao=repo.dt_geracao(),
    )
