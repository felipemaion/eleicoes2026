"""Caso de uso /comparativo: evolução 2022→2026 por AMC e KPIs do grupo."""

from collections.abc import Sequence

import polars as pl
from indicadores import evolucao, financeiro, grupos
from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Cargo, Indicador
from api.erros import nao_encontrado, parametro_invalido
from api.fontes import Fonte, fontes
from api.repositorio.base import DadosIndisponiveis, Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.contas import ANO_NOMINAL, ContasAgregadas, contas_de, correcao_do_ano
from api.servicos.grupos import Catalogo, DefinicaoGrupo, candidaturas_do_grupo
from api.servicos.mapa import EscalaSugerida, Linha, escala_comum


class GrupoRef(BaseModel):
    """Grupo de um dos lados da comparação."""

    id: str
    rotulo: str
    ano: int


class EvolucaoMunicipio(BaseModel):
    """Evolução numa AMC (município IBGE com desmembramentos agregados, §5.1)."""

    cd_amc: int
    nome: str
    uf: str
    penetracao_de: float | None
    penetracao_para: float | None
    delta_penetracao: float | None = Field(description="‰ — métrica-âncora.")
    swing_pp: float | None = Field(description="p.p. de votos válidos.")
    retencao: float | None = Field(description="votos_para / votos_de; null se votos_de = 0.")
    ganho_absoluto: int | None = Field(description="null se a AMC só existe num dos anos.")
    votos_de: int | None
    votos_para: int | None


class KpisComparativo(BaseModel):
    """Os mesmos indicadores sobre o recorte inteiro (Σ votos / Σ base, não média de AMCs)."""

    penetracao_de: float | None
    penetracao_para: float | None
    delta_penetracao: float | None
    swing_pp: float | None
    retencao: float | None
    ganho_absoluto: int | None
    votos_de: int | None
    votos_para: int | None


class IndicadorComparado(BaseModel):
    """Um indicador de receita nos dois anos (spec §4.10)."""

    de_nominal: float | None = Field(description="Valor do ano 'de' como o TSE publicou.")
    de: float | None = Field(
        description="Valor do ano 'de' em R$ do mês-base (monetário) ou igual ao nominal (%)."
    )
    para: float | None
    delta: float | None = Field(description="para − de (R$ do mês-base, ou p.p. nos percentuais).")
    var_pct: float | None = Field(description="100 × (para / de − 1); só monetários.")


class ComparativoReceitas(BaseModel):
    """Receitas do grupo 'de' × 'para', 2022 deflacionado ao mês-base."""

    base_ipca: str = Field(description="Mês-base (AAAA-MM) em que o ano 'de' foi corrigido.")
    contas_parciais_de: bool
    contas_parciais_para: bool = Field(
        description="2026 parcial: queda de receita é esperada até a prestação final (§4.10)."
    )
    monetarios: dict[str, IndicadorComparado] = Field(
        description="receita_total, receita_<categoria>, receita_por_voto, receita_por_mil_aptos, "
        "receita_media_candidato, receita_mediana_candidato."
    )
    percentuais: dict[str, IndicadorComparado] = Field(
        description="pct_publico, pct_autofinanciamento, pct_pessoa_fisica, pct_estimavel."
    )


class Comparativo(BaseModel):
    """Corpo de GET /comparativo."""

    comparacao: str
    rotulo: str
    de: GrupoRef
    para: GrupoRef
    cargo: str
    uf: str | None
    mesmos_candidatos: bool
    n_de: int | None = Field(
        description="Candidaturas aptas do lado 'de'; null = situação não publicada."
    )
    n_para: int | None
    kpis: KpisComparativo
    escala_sugerida: EscalaSugerida = Field(
        description="Quebras comuns 2022+2026 da penetração municipal (as dos dois mapas)."
    )
    municipios: list[EvolucaoMunicipio]
    receitas: ComparativoReceitas | None = Field(
        description="Receitas 2022→2026 deflacionadas; null se algum lado não tem contas."
    )
    dt_geracao: str
    fontes: list[Fonte] = Field(description="Procedência dos números (arquivo, regra, spec).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "comparacao": "evolucao_mbl",
                    "rotulo": "MBL 2022 → MBL 2026",
                    "de": {"id": "mbl_2022", "rotulo": "MBL 2022", "ano": 2022},
                    "para": {"id": "mbl_2026", "rotulo": "MBL 2026", "ano": 2026},
                    "cargo": "DEPUTADO FEDERAL",
                    "uf": "SP",
                    "mesmos_candidatos": False,
                    "n_de": 3,
                    "n_para": 3,
                    "kpis": {
                        "penetracao_de": 70.3,
                        "penetracao_para": 107.4,
                        "delta_penetracao": 37.1,
                        "swing_pp": 5.9,
                        "retencao": 1.62,
                        "ganho_absoluto": 720,
                        "votos_de": 1160,
                        "votos_para": 1880,
                    },
                    "municipios": [],
                    "receitas": None,
                    "dt_geracao": "2026-10-06",
                    "fontes": [],
                }
            ]
        }
    )


def _lado(
    repo: Repositorio, grupo: DefinicaoGrupo, cargo: str, uf: str | None
) -> list[Candidatura]:
    return candidaturas_do_grupo(repo, grupo, uf=uf, cargo=cargo)


ANO_DE, ANO_PARA = 2022, 2026  # anos da seleção do usuário (`pessoas`, `sq_2022`, `sq_2026`)
ID_SELECAO = "selecao"


_ESQUEMA = {"cd_mun_ibge": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64, "votos": pl.Int64}


def _quadro(
    repo: Repositorio, ano: int, cargo: str, uf: str | None, sqs: Sequence[int]
) -> pl.DataFrame:
    """`cd_mun_ibge, aptos, validos, votos` de todos os municípios do recorte (zero explícito)."""
    # Exterior (sem município IBGE) não tem AMC: fica fora da evolução municipal.
    votos = {
        v.cd_mun_ibge: v.votos
        for v in repo.votos_territorio(ano, sqs, por_zona=False, uf=uf)
        if v.cd_mun_ibge is not None
    }
    return pl.DataFrame(
        [
            (b.cd_mun_ibge, b.aptos, b.validos, votos.get(b.cd_mun_ibge, 0))
            for b in repo.base_eleitoral(ano, cargo, por_zona=False, uf=uf)
            if b.cd_mun_ibge is not None
        ],
        schema=_ESQUEMA,
        orient="row",
    )


def _linhas_municipais(quadro: pl.DataFrame) -> list[Linha]:
    """Mesmas linhas que /mapa (nível município) monta, para a escala ser idêntica."""
    return [
        (str(r["cd_mun_ibge"]), r["votos"], r["aptos"], r["validos"]) for r in quadro.to_dicts()
    ]


def _pessoas(candidaturas: Sequence[Candidatura], votos: dict[int, int]) -> pl.DataFrame:
    return pl.DataFrame(
        [(c.pessoa_id, votos.get(c.sq_candidato, 0)) for c in candidaturas],
        schema={"pessoa_id": pl.String, "votos": pl.Int64},
        orient="row",
    )


def _n_aptas(candidaturas: Sequence[Candidatura]) -> int | None:
    """Aptas do lado; `None` se o TSE ainda não publicou a situação (0 seria dado falso)."""
    if candidaturas and all(c.ds_situacao_candidatura is None for c in candidaturas):
        return None
    quadro = pl.DataFrame(
        [(c.sq_candidato, c.ds_situacao_candidatura) for c in candidaturas],
        schema={"sq_candidato": pl.Int64, "ds_situacao_candidatura": pl.String},
        orient="row",
    )
    return int(grupos.n_candidatos(quadro, [c.sq_candidato for c in candidaturas]).item())


def _selecao(
    repo: Repositorio,
    cargo: Cargo,
    uf: str | None,
    *,
    pessoas: Sequence[str],
    sq_de: Sequence[int],
    sq_para: Sequence[int],
) -> tuple[list[Candidatura], list[Candidatura]]:
    """Candidaturas escolhidas pelo usuário, por pessoa (nos dois anos) e/ou por `sq_candidato`.

    `pessoas` só vale para quem concorreu ao cargo nos dois anos; `sq_*` é escolha explícita.
    """
    de = {c.sq_candidato: c for c in repo.candidaturas_de_pessoas(ANO_DE, pessoas)}
    para = {c.sq_candidato: c for c in repo.candidaturas_de_pessoas(ANO_PARA, pessoas)}

    def no_recorte(c: Candidatura) -> bool:
        return c.ds_cargo == cargo.value and (uf is None or c.sg_uf in (uf, "BR"))

    de = {sq: c for sq, c in de.items() if no_recorte(c)}
    para = {sq: c for sq, c in para.items() if no_recorte(c)}
    if pessoas:  # pessoa que não está nos dois lados não forma par
        comuns = {c.pessoa_id for c in de.values()} & {c.pessoa_id for c in para.values()}
        de = {sq: c for sq, c in de.items() if c.pessoa_id in comuns}
        para = {sq: c for sq, c in para.items() if c.pessoa_id in comuns}
    for ano, sqs, destino in ((ANO_DE, sq_de, de), (ANO_PARA, sq_para, para)):
        for sq in sqs:
            c = repo.candidatura(ano, sq)
            if c is None:
                raise nao_encontrado("candidato_nao_encontrado", f"candidato {ano}/{sq}")
            if no_recorte(c):
                destino[sq] = c
    return list(de.values()), list(para.values())


_MONETARIOS_FIXOS = (
    "receita_total",
    "receita_por_voto",
    "receita_por_mil_aptos",
    "receita_media_candidato",
    "receita_mediana_candidato",
)
_PERCENTUAIS = ("pct_publico", "pct_autofinanciamento", "pct_pessoa_fisica", "pct_estimavel")


def _indicadores_do_lado(contas: ContasAgregadas) -> dict[str, float | None]:
    """Indicadores de receita de um lado, nominais, com os nomes que a lib compara."""
    rec = contas.receitas
    return {
        "receita_total": rec.receita_total,
        **{f"receita_{c}": rec.por_categoria.get(c, 0.0) for c in financeiro.CATEGORIAS_RECEITA},
        "receita_por_voto": contas.receita_por_voto.receita_por_voto,
        "receita_por_mil_aptos": contas.receita_por_mil_aptos,
        "receita_media_candidato": contas.distribuicao.media,
        "receita_mediana_candidato": contas.distribuicao.mediana,
        **{p: getattr(rec, p) for p in _PERCENTUAIS},
    }


def _comparar_receitas(
    repo: Repositorio,
    de: GrupoRef,
    para: GrupoRef,
    c_de: Sequence[Candidatura],
    c_para: Sequence[Candidatura],
) -> ComparativoReceitas | None:
    """Compara as receitas dos dois lados com `comparar_receitas` (2022 nominal → mês-base)."""
    if not (de.ano < ANO_NOMINAL <= para.ano):
        return None  # só 2022→2026 tem correção definida (ADR 0007)
    lado_de = contas_de(repo, de.ano, c_de, nominal=True)
    lado_para = contas_de(repo, para.ano, c_para)
    if not lado_de.por_candidato or not lado_para.por_candidato:
        return None
    correcao = correcao_do_ano(repo, de.ano)
    assert correcao is not None  # noqa: S101 - de.ano < ANO_NOMINAL garante a série
    serie, origem, base = correcao
    v_de, v_para = _indicadores_do_lado(lado_de), _indicadores_do_lado(lado_para)
    monetarios = [*(c for c in v_de if c not in _PERCENTUAIS)]
    quadro = pl.DataFrame(
        {
            **{f"{c}_2022": [v_de[c]] for c in v_de},
            **{f"{c}_2026": [v_para[c]] for c in v_para},
        },
        schema={f"{c}_{a}": pl.Float64 for c in v_de for a in (2022, 2026)},
    )
    try:
        r = financeiro.comparar_receitas(
            quadro, monetarios, _PERCENTUAIS, serie, origem, base
        ).to_dicts()[0]
    except ValueError as erro:
        raise DadosIndisponiveis(str(erro)) from erro

    def indicador(c: str, *, monetario: bool) -> IndicadorComparado:
        return IndicadorComparado(
            de_nominal=v_de[c],
            de=r[f"{c}_2022"],
            para=r[f"{c}_2026"],
            delta=r[f"delta_{c}"],
            var_pct=r[f"var_pct_{c}"] if monetario else None,
        )

    return ComparativoReceitas(
        base_ipca=base,
        contas_parciais_de=repo.tp_prestacao_contas(de.ano).upper() == "PARCIAL",
        contas_parciais_para=repo.tp_prestacao_contas(para.ano).upper() == "PARCIAL",
        monetarios={c: indicador(c, monetario=True) for c in monetarios},
        percentuais={c: indicador(c, monetario=False) for c in _PERCENTUAIS},
    )


def montar_comparativo(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    comparacao_id: str | None,
    cargo: Cargo,
    uf: str | None,
    mesmos_candidatos: bool,
    pessoas: Sequence[str] = (),
    sq_2022: Sequence[int] = (),
    sq_2026: Sequence[int] = (),
) -> Comparativo:
    """Evolução do grupo `de` para `para`, ou de uma seleção do usuário (pessoas/sqs).

    Com `comparacao_id`, opcionalmente só as mesmas pessoas (`pessoa_id`). Sem par comparável
    (um lado sem candidaturas no cargo/UF) → 422, nunca um comparativo vazio ou erro interno.
    """
    escolheu = bool(pessoas or sq_2022 or sq_2026)
    if comparacao_id is not None and escolheu:
        raise parametro_invalido(
            "comparacao_e_selecao", "use 'comparacao' ou 'pessoas'/'sq_2022'/'sq_2026', não ambos"
        )
    if comparacao_id is None and not escolheu:
        raise parametro_invalido(
            "comparativo_sem_alvo", "informe 'comparacao' ou 'pessoas'/'sq_2022'/'sq_2026'"
        )
    if cargo is Cargo.SENADOR:
        # 2022 elegeu 1 vaga (1 voto) e 2026 elege 2 (2 votos): taxas incomparáveis (§1.8).
        raise parametro_invalido(
            "cargo_sem_evolucao", "Senado não entra em evolução 2022→2026 (1 voto × 2 votos)"
        )
    if comparacao_id is None:
        c_de, c_para = _selecao(repo, cargo, uf, pessoas=pessoas, sq_de=sq_2022, sq_para=sq_2026)
        id_comp, rotulo = ID_SELECAO, "Seleção do usuário"
        de = GrupoRef(id=ID_SELECAO, rotulo="Seleção 2022", ano=ANO_DE)
        para = GrupoRef(id=ID_SELECAO, rotulo="Seleção 2026", ano=ANO_PARA)
        mesmos_candidatos = False  # a escolha já é do usuário
    else:
        comp = catalogo.comparacao(comparacao_id)
        g_de, g_para = catalogo.grupo(comp.de), catalogo.grupo(comp.para)
        c_de, c_para = _lado(repo, g_de, cargo.value, uf), _lado(repo, g_para, cargo.value, uf)
        id_comp, rotulo = comp.id, comp.rotulo
        de = GrupoRef(id=g_de.id, rotulo=g_de.rotulo, ano=g_de.ano)
        para = GrupoRef(id=g_para.id, rotulo=g_para.rotulo, ano=g_para.ano)
    if not c_de or not c_para:
        lado = de.rotulo if not c_de else para.rotulo
        raise parametro_invalido(
            "sem_par_comparavel",
            f"'{lado}' não tem candidaturas a {cargo.value}"
            f"{' em ' + uf if uf else ''}: não há o que comparar",
        )
    if mesmos_candidatos:
        v_de = repo.votos_totais(de.ano, [c.sq_candidato for c in c_de])
        v_para = repo.votos_totais(para.ano, [c.sq_candidato for c in c_para])
        comuns = set(
            evolucao.mesmos_candidatos(_pessoas(c_de, v_de), _pessoas(c_para, v_para))[
                "pessoa_ids"
            ].item()
        )
        c_de = [c for c in c_de if c.pessoa_id in comuns]
        c_para = [c for c in c_para if c.pessoa_id in comuns]
    q_de = _quadro(repo, de.ano, cargo.value, uf, [c.sq_candidato for c in c_de])
    q_para = _quadro(repo, para.ano, cargo.value, uf, [c.sq_candidato for c in c_para])
    codigos = sorted(set(q_de["cd_mun_ibge"]) | set(q_para["cd_mun_ibge"]))
    municipios = {m.cd_mun_ibge: m for m in repo.municipios(codigos)}
    crosswalk = pl.DataFrame(
        [(k, m.cd_amc) for k, m in municipios.items()],
        schema={"cd_mun_ibge": pl.Int64, "amc": pl.Int64},
        orient="row",
    )
    todos = pl.DataFrame(
        {"cd_mun_ibge": codigos, "amc": [0] * len(codigos)}, schema=crosswalk.schema
    )
    try:
        por_amc = evolucao.evolucao(q_de, q_para, crosswalk, cd_cargo=cargo.codigo)
        # Recorte inteiro como uma AMC só: Σ votos / Σ base, não média de AMCs.
        total = evolucao.evolucao(q_de, q_para, todos, cd_cargo=cargo.codigo)
    except ValueError as erro:  # município sem AMC: dado inconsistente
        raise DadosIndisponiveis(str(erro)) from erro
    cabecas = {m.cd_mun_ibge: m for m in repo.municipios(por_amc["amc"].to_list())}
    if any(a not in cabecas for a in por_amc["amc"]):
        raise DadosIndisponiveis("AMC sem município de referência")
    kpis = total.to_dicts()[0] if total.height else {}
    receitas = _comparar_receitas(repo, de, para, c_de, c_para)
    return Comparativo(
        comparacao=id_comp,
        rotulo=rotulo,
        de=de,
        para=para,
        cargo=cargo.value,
        uf=uf,
        mesmos_candidatos=mesmos_candidatos,
        n_de=_n_aptas(c_de),
        n_para=_n_aptas(c_para),
        kpis=KpisComparativo(
            penetracao_de=kpis.get("penetracao_2022"),
            penetracao_para=kpis.get("penetracao_2026"),
            delta_penetracao=kpis.get("delta_penetracao"),
            swing_pp=kpis.get("swing_pp"),
            retencao=kpis.get("retencao"),
            ganho_absoluto=kpis.get("ganho_absoluto"),
            votos_de=kpis.get("votos_2022"),
            votos_para=kpis.get("votos_2026"),
        ),
        escala_sugerida=escala_comum(
            {
                de.ano: _linhas_municipais(q_de),
                para.ano: _linhas_municipais(q_para),
            },
            Indicador.PENETRACAO,
        ),
        municipios=[
            EvolucaoMunicipio(
                cd_amc=e["amc"],
                nome=cabecas[e["amc"]].nome,
                uf=cabecas[e["amc"]].uf,
                penetracao_de=e["penetracao_2022"],
                penetracao_para=e["penetracao_2026"],
                delta_penetracao=e["delta_penetracao"],
                swing_pp=e["swing_pp"],
                retencao=e["retencao"],
                ganho_absoluto=e["ganho_absoluto"],
                votos_de=e["votos_2022"],
                votos_para=e["votos_2026"],
            )
            for e in por_amc.to_dicts()
        ],
        receitas=receitas,
        dt_geracao=repo.dt_geracao(),
        fontes=[
            f
            for ano in (de.ano, para.ano)
            for f in fontes(
                ["votacao_candidato_munzona", "detalhe_votacao_munzona"]
                + (["prestacao_contas"] if receitas else [])
                + (["ipca"] if receitas and ano == de.ano else []),
                ano=ano,
                dt_geracao=repo.dt_geracao(),
            )
        ],
    )
