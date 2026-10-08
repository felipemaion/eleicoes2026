"""Casos de uso /mapa e /mapa/pontos: valores por território para o coroplético e a densidade."""

from collections.abc import Mapping, Sequence

import polars as pl
from indicadores import desempenho, espacial
from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Indicador, Nivel
from api.erros import parametro_invalido
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura, VotosSemCoordenada
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
    nome: str | None = Field(
        default=None,
        description="Nome do município (também nas chaves `IBGE-zona`); null no H3 ou se o "
        "município não consta do cadastro.",
    )


class EscalaSugerida(BaseModel):
    """Sugestão de classes para a legenda (spec §8.2); o front decide a cor final."""

    tipo: str = Field(description="`sequencial` (taxas) ou `simbolo_proporcional` (absolutos).")
    paleta: str
    quebras: list[float] | None = Field(
        description="Cortes internos da legenda; null quando não há como calcular (ver `aviso`)."
    )
    aviso: str | None = Field(default=None, description="Por que `quebras` é null, se for.")
    anos: list[int] = Field(
        default_factory=list,
        description="Anos cujos valores entraram nas quebras (2022+2026 numa comparação).",
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
    votos_sem_coordenada: int | None = Field(
        default=None,
        description="Só no H3: votos do recorte em locais sem coordenada, que não aparecem "
        "em nenhuma célula. null nos demais níveis.",
    )
    pct_votos_sem_coordenada: float | None = Field(
        default=None,
        description="`votos_sem_coordenada` em % dos votos do recorte (o front avisa se > 5%).",
    )
    votos_fora_do_mapa: int = Field(
        default=0,
        description="Votos do recorte sem município IBGE (exterior, `ZZ`): contam no total do "
        "candidato, mas não têm polígono e ficam fora de `valores`.",
    )
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


GRADE_NACIONAL_GRAUS = 0.1  # ≈ 11 km na latitude: ordem de milhares de células para o país
Linha = tuple[str, int, int, int | None]  # (chave, votos, aptos, válidos)
_CLASSES = 5  # quintis; quebras_comuns reduz se os dados empatarem


def quebras_da_escala(
    linhas_por_ano: Mapping[int, Sequence[Linha]], indicador: Indicador
) -> tuple[list[float] | None, str | None]:
    """Cortes da legenda comuns a todos os anos (spec §8.2), sem unidades de n baixo (§1.4).

    Delega a `indicadores.espacial.quebras_comuns`. Dados insuficientes (< 2k valores ou sem
    variação) viram `(None, aviso)`: o chamador explica ao usuário, nunca devolve lista inventada.
    """
    tabelas = {ano: _tabela_escala(linhas, indicador) for ano, linhas in linhas_por_ano.items()}
    try:
        return espacial.quebras_comuns(tabelas, k=_CLASSES), None
    except ValueError as erro:
        return None, f"sem base para quebras comuns: {erro}"


def _tabela_escala(linhas: Sequence[Linha], indicador: Indicador) -> pl.DataFrame:
    """`valor` (taxa do indicador) e `n_baixo` por território, pela biblioteca de indicadores."""
    quadro = _quadro(linhas)
    calculado = desempenho.penetracao(desempenho.pct_validos(quadro))
    total_aptos = int(quadro["aptos"].sum())
    # Taxa de referência = penetração do recorte inteiro (proporção), base do esperado (§1.4).
    taxa_ref = int(quadro["votos"].sum()) / total_aptos if total_aptos else None
    calculado = calculado.with_columns(pl.lit(taxa_ref, dtype=pl.Float64).alias("taxa_referencia"))
    coluna = {Indicador.PENETRACAO: "penetracao", Indicador.PCT_VALIDOS: "pct_validos"}[indicador]
    return espacial.n_baixo(calculado).select(pl.col(coluna).alias("valor"), "n_baixo")


def escala_comum(
    linhas_por_ano: Mapping[int, Sequence[Linha]], indicador: Indicador
) -> EscalaSugerida:
    """Escala do indicador para os anos dados; absolutos viram símbolo proporcional."""
    if indicador is Indicador.VOTOS:
        return EscalaSugerida(
            tipo="simbolo_proporcional",
            paleta="um_matiz",
            quebras=[],
            anos=sorted(linhas_por_ano),
        )
    quebras, aviso = quebras_da_escala(linhas_por_ano, indicador)
    return EscalaSugerida(
        tipo="sequencial",
        paleta="viridis",
        quebras=quebras,
        aviso=aviso,
        anos=sorted(linhas_por_ano),
    )


def _outro_lado(catalogo: Catalogo, comparacao_id: str, grupo_id: str | None) -> tuple[str, int]:
    """Grupo e ano do outro lado da comparação (`de` ↔ `para`)."""
    comp = catalogo.comparacao(comparacao_id)
    if grupo_id not in (comp.de, comp.para):
        raise parametro_invalido(
            "comparacao_sem_grupo",
            f"com 'comparacao', 'grupo' deve ser '{comp.de}' ou '{comp.para}'",
        )
    outro = comp.para if grupo_id == comp.de else comp.de
    return outro, catalogo.grupo(outro).ano


def _coletar(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    nivel: Nivel,
    grupo_id: str | None,
    sq_candidato: int | None,
) -> tuple[list[Candidatura], list[Linha], int]:
    """Candidaturas, linhas (chave, votos, aptos, válidos) por território e votos sem município."""
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    sqs = [c.sq_candidato for c in alvo]
    if nivel is Nivel.H3:
        assert uf is not None  # noqa: S101 - exigido por quem chama
        return alvo, [(c.h3, c.votos, c.aptos, None) for c in repo.votos_h3(ano, sqs, uf=uf)], 0
    por_zona = nivel is Nivel.ZONA
    votos: dict[tuple[int, int | None], int] = {}
    fora_do_mapa = 0
    for v in repo.votos_territorio(ano, sqs, por_zona=por_zona, uf=uf):
        if v.cd_mun_ibge is None:  # exterior: sem município IBGE, logo sem polígono
            fora_do_mapa += v.votos
        else:
            votos[(v.cd_mun_ibge, v.nr_zona)] = v.votos
    base = [
        (b.cd_mun_ibge, b.nr_zona, b.aptos, b.validos)
        for b in repo.base_eleitoral(ano, cargo, por_zona=por_zona, uf=uf)
        if b.cd_mun_ibge is not None
    ]
    vistos = {(m, z) for m, z, _, _ in base}
    linhas: list[Linha] = [
        (_chave(m, z), votos.get((m, z), 0), aptos, validos) for m, z, aptos, validos in base
    ]
    # Voto sem base eleitoral: aparece como "sem dado" (aptos 0 → null), não some.
    linhas += [(_chave(m, z), n, 0, 0) for (m, z), n in votos.items() if (m, z) not in vistos]
    return alvo, linhas, fora_do_mapa


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
    comparacao: str | None = None,
) -> Mapa:
    """Indicador por território; com aptos e sem voto = 0, sem aptos = null (nunca inf).

    Com `comparacao`, a escala usa quebras comuns ao ano pedido e ao do outro lado dela.
    """
    if nivel is not Nivel.MUNICIPIO and uf is None:
        raise parametro_invalido("uf_obrigatoria", f"nivel={nivel.value} exige 'uf'")
    if nivel is Nivel.H3 and indicador is Indicador.PCT_VALIDOS:
        raise parametro_invalido(
            "indicador_indisponivel", "pct_validos não existe no H3; use penetracao ou votos"
        )
    if comparacao is not None and sq_candidato is not None:
        raise parametro_invalido("comparacao_com_candidato", "'comparacao' vale só para 'grupo'")
    outro = _outro_lado(catalogo, comparacao, grupo_id) if comparacao else None
    alvo, linhas, fora_do_mapa = _coletar(
        repo,
        catalogo,
        ano=ano,
        cargo=cargo,
        uf=uf,
        nivel=nivel,
        grupo_id=grupo_id,
        sq_candidato=sq_candidato,
    )
    por_ano = {ano: linhas}
    if outro is not None:
        grupo_outro, ano_outro = outro
        por_ano[ano_outro] = _coletar(
            repo,
            catalogo,
            ano=ano_outro,
            cargo=cargo,
            uf=uf,
            nivel=nivel,
            grupo_id=grupo_outro,
            sq_candidato=None,
        )[1]
    detalhes = _detalhes(indicador, linhas, _nomes(repo, nivel, linhas))
    sem_coord = (
        repo.votos_sem_coordenada(ano, [c.sq_candidato for c in alvo], uf=uf, por_h3=True)
        if nivel is Nivel.H3 and uf is not None
        else None
    )
    return Mapa(
        ano=ano,
        nivel=nivel.value,
        indicador=indicador.value,
        valores={k: d.taxa for k, d in detalhes.items()},
        detalhes=detalhes,
        escala_sugerida=escala_comum(por_ano, indicador),
        unidade=_UNIDADE[indicador],
        denominador=_DENOMINADOR[indicador],
        n_candidaturas=len(alvo),
        votos_sem_coordenada=None if sem_coord is None else sem_coord.sem_coordenada,
        pct_votos_sem_coordenada=None if sem_coord is None else _pct(sem_coord),
        votos_fora_do_mapa=fora_do_mapa,
        dt_geracao=repo.dt_geracao(),
    )


def _quadro(linhas: Sequence[Linha]) -> pl.DataFrame:
    return pl.DataFrame(
        list(linhas),
        schema={"chave": pl.String, "votos": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64},
        orient="row",
    )


def _nomes(repo: Repositorio, nivel: Nivel, linhas: Sequence[Linha]) -> dict[int, str]:
    """Nome por código IBGE dos municípios das `linhas` (vazio no H3, que não tem município)."""
    if nivel is Nivel.H3:
        return {}
    codigos = sorted({_cd_mun(chave) for chave, *_ in linhas})
    return {m.cd_mun_ibge: m.nome for m in repo.municipios(codigos)}


def _cd_mun(chave: str) -> int:
    """Código IBGE de uma chave `IBGE` ou `IBGE-zona`."""
    return int(chave.split("-", 1)[0])


def _detalhes(
    indicador: Indicador, linhas: Sequence[Linha], nomes: Mapping[int, str]
) -> dict[str, Detalhe]:
    """Taxas de todos os territórios de uma vez, pela biblioteca de indicadores."""
    calculado = desempenho.penetracao(desempenho.pct_validos(_quadro(linhas)))
    coluna = {
        Indicador.PENETRACAO: "penetracao",
        Indicador.PCT_VALIDOS: "pct_validos",
        Indicador.VOTOS: "votos",
    }[indicador]
    return {
        r["chave"]: Detalhe(
            votos=r["votos"],
            aptos=r["aptos"],
            validos=r["validos"],
            taxa=None if r[coluna] is None else float(r[coluna]),
            nome=nomes.get(_cd_mun(r["chave"])) if nomes else None,
        )
        for r in calculado.to_dicts()
    }


def _chave(cd_mun_ibge: int, nr_zona: int | None) -> str:
    return str(cd_mun_ibge) if nr_zona is None else f"{cd_mun_ibge}-{nr_zona}"


def _pct(v: VotosSemCoordenada) -> float:
    """% de votos sem coordenada; 0 se o recorte não tem voto (sem divisão por zero)."""
    return round(100 * v.sem_coordenada / v.total, 2) if v.total else 0.0


class Ponto(BaseModel):
    """Local de votação."""

    lat: float
    lon: float
    votos: int


class Pontos(BaseModel):
    """Corpo de GET /mapa/pontos (densidade de votos por local)."""

    ano: int
    total: int = Field(description="Pontos no recorte (locais com voto ou, na grade, células).")
    grade_graus: float | None = Field(
        description="Sem `uf` (Brasil): tamanho em graus da célula lat/lon em que os locais são "
        "somados (cada ponto é o centroide ponderado por votos). null = um ponto por local."
    )
    limite: int
    offset: int
    truncado: bool = Field(description="Há mais páginas além desta.")
    votos_sem_coordenada: int = Field(
        description="Votos do recorte (UF inteira, não só a página) em locais sem coordenada, "
        "que não viram ponto."
    )
    pct_votos_sem_coordenada: float = Field(
        description="`votos_sem_coordenada` em % dos votos do recorte (o front avisa se > 5%)."
    )
    pontos: list[Ponto]
    dt_geracao: str


def montar_pontos(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    ano: int,
    cargo: str,
    uf: str | None,
    grupo_id: str | None,
    sq_candidato: int | None,
    limite: int,
    offset: int,
) -> Pontos:
    """Locais de votação com voto, mais votados primeiro, paginados.

    Sem `uf` (Brasil, p.ex. presidente) os ~150 mil locais viriam todos de uma vez: soma-se em
    células de `GRADE_NACIONAL_GRAUS`, um volume que o mapa renderiza.
    """
    alvo = selecionar_alvo(
        repo, catalogo, ano=ano, cargo=cargo, uf=uf, grupo_id=grupo_id, sq_candidato=sq_candidato
    )
    grade = GRADE_NACIONAL_GRAUS if uf is None else None
    total, linhas = repo.pontos(
        ano, [c.sq_candidato for c in alvo], uf=uf, limite=limite, offset=offset, grade_graus=grade
    )
    sem_coord = repo.votos_sem_coordenada(ano, [c.sq_candidato for c in alvo], uf=uf, por_h3=False)
    return Pontos(
        ano=ano,
        total=total,
        grade_graus=grade,
        limite=limite,
        offset=offset,
        truncado=offset + len(linhas) < total,
        votos_sem_coordenada=sem_coord.sem_coordenada,
        pct_votos_sem_coordenada=_pct(sem_coord),
        pontos=[Ponto(lat=p.lat, lon=p.lon, votos=p.votos) for p in linhas],
        dt_geracao=repo.dt_geracao(),
    )
