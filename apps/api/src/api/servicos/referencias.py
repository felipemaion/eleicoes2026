"""Caso de uso /referencias: candidatos do Missão × grupo de referência, lado a lado.

Nenhuma fórmula eleitoral aqui: votos, taxas, concentração e finanças vêm de
`packages/indicadores` (via `candidatos.taxas`, `desempenho`, `espacial` e `contas_de`).
A mediana da referência e o índice relativo (nosso ÷ mediana) vêm de
`indicadores.referencias` (spec §10.3, T-A11); a API só traduz nomes e monta o JSON.
"""

import polars as pl
from indicadores import desempenho, espacial
from indicadores._colunas import CD_CARGO
from indicadores._comum import razao
from indicadores.referencias import PERFIL, mediana_referencia, perfil_relativo
from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Cargo
from api.erros import parametro_invalido
from api.fontes import Fonte, fontes
from api.fotos import ComFotoELink, foto_e_link
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.candidatos import Partido, taxas
from api.servicos.contas import ContasAgregadas, ContasCand, contas_de
from api.servicos.escopo import BasesPorEscopo, uf_da_base
from api.servicos.grupos import Catalogo, DefinicaoGrupo, candidaturas_do_grupo
from api.servicos.ranking import selecionar_ranking

CAMPOS = (
    "votos",
    "pct_validos",
    "penetracao",
    "n_municipios",
    "pct_maiores",
    "hhi",
    "n_efetivo_municipios",
    "custo_voto_pago",
    "receita_total",
    "receita_por_voto",
    "pct_publico",
    "pct_pessoa_fisica",
    "pct_autofinanciamento",
)
_FINANCAS = (
    "custo_voto_pago", "receita_total", "receita_por_voto", "pct_publico", "pct_pessoa_fisica",
    "pct_autofinanciamento",
)  # fmt: skip
# Nome na API → nome no catálogo `PERFIL` da biblioteca (só `n_municipios` difere). Campo fora do
# catálogo (hhi: o catálogo usa o seu inverso `n_efetivo_municipios`) não tem
# mediana nem índice: ficam nulos, com `n_mediana` 0.
_NO_CATALOGO = {"n_municipios": "n_municipios_com_voto"}
_COMPARAVEIS = tuple(c for c in CAMPOS if _NO_CATALOGO.get(c, c) in PERFIL)
_CARGO_CURTO = {
    "PRESIDENTE": "Presidente",
    "GOVERNADOR": "Governador",
    "SENADOR": "Senador",
    "DEPUTADO FEDERAL": "Dep. federal",
    "DEPUTADO ESTADUAL": "Dep. estadual",
    "DEPUTADO DISTRITAL": "Dep. distrital",
}


class Perfil(BaseModel):
    """Indicadores comparáveis (taxas ou normalizados). Nulo = ausente, nunca zero."""

    votos: float | None = Field(description="Votos nominais válidos (§2.1).")
    pct_validos: float | None = Field(description="% dos válidos do cargo na circunscrição (§2.2).")
    penetracao: float | None = Field(description="‰ dos aptos do cargo na circunscrição (§2.3).")
    n_municipios: float | None = Field(description="Municípios com ao menos um voto.")
    pct_maiores: float | None = Field(
        description="% dos votos vindos dos 10 maiores municípios do candidato (§10.2)."
    )
    hhi: float | None = Field(description="Concentração geográfica (HHI entre municípios, §3.2).")
    n_efetivo_municipios: float | None = Field(description="1 / HHI: municípios equivalentes.")
    custo_voto_pago: float | None = Field(description="R$/voto pago, sem repasses (§4.2).")
    receita_total: float | None = Field(description="Receita bruta em R$ (IPCA em 2022).")
    receita_por_voto: float | None = Field(description="R$ de receita por voto (§4.7).")
    pct_publico: float | None = Field(description="FEFC + Fundo Partidário, % da receita.")
    pct_autofinanciamento: float | None = Field(description="Recursos próprios, % da receita.")
    pct_pessoa_fisica: float | None = Field(
        description="Doações de pessoas físicas e financiamento coletivo, % da receita."
    )


class CandidatoComparado(ComFotoELink):
    """Candidato com identificação, resultado e indicadores comparáveis."""

    ano: int
    sq_candidato: int
    nm_urna: str
    sg_uf: str
    cargo: str
    partido: Partido
    resultado: str | None = Field(description="`ds_sit_tot_turno`; null se sem apuração.")
    votos: int
    destacado: bool = Field(description="É o candidato pedido em `sq`.")
    indicadores: Perfil
    motivos: dict[str, str] = Field(
        description="Para cada indicador nulo, por que não há valor (ex.: sem prestação de contas)."
    )
    indices: Perfil | None = Field(
        description="Só nos nossos: indicador ÷ mediana da referência (1 = igual à mediana). "
        "Nulo se um dos dois falta ou a mediana é zero."
    )


class Lado(BaseModel):
    """Um dos dois lados da comparação."""

    rotulo: str
    grupo_id: str
    candidatos: list[CandidatoComparado]
    mediana: Perfil = Field(description="Mediana dos candidatos do lado, ignorando nulos.")
    n_mediana: dict[str, int] = Field(description="Candidatos que entraram na mediana, por campo.")
    motivo_vazio: str | None = Field(description="Por que não há candidatos neste lado.")


class Referencias(BaseModel):
    """Corpo de GET /referencias."""

    ano: int
    cargo: str
    uf: str | None = Field(description="UF do recorte; null para presidente (nacional).")
    rotulo: str = Field(description="Frase pronta: quem está sendo comparado com quem.")
    destaque: int | None
    nossos: Lado
    referencia: Lado
    contas_parciais: bool
    base_ipca: str | None
    dt_geracao: str
    fontes: list[Fonte]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ano": 2026,
                    "cargo": "DEPUTADO ESTADUAL",
                    "uf": "SP",
                    "rotulo": "Missão · Dep. estadual · SP × 5 eleitos mais votados de outros "
                    "partidos em SP",
                    "destaque": None,
                    "nossos": {"rotulo": "Missão · Dep. estadual · SP", "candidatos": "…"},
                    "referencia": {"rotulo": "5 eleitos mais votados de outros partidos em SP"},
                }
            ]
        }
    )


def _grupo_aplicavel(
    repo: Repositorio, catalogo: Catalogo, cargo: str
) -> tuple[DefinicaoGrupo, DefinicaoGrupo]:
    """(nossos, referência) do cargo, pela configuração; sem par → 422."""
    config = catalogo.referencias
    if config is None:
        raise parametro_invalido("sem_referencias", "config/grupos.yaml não define `referencias`")
    nossos = catalogo.grupo(config.nossos)
    for gid in config.contra:
        grupo = catalogo.grupo(gid)
        if grupo.ano != nossos.ano:
            continue
        if grupo.ranking is not None:
            if cargo in grupo.ranking.cargos:
                return nossos, grupo
        elif repo.candidaturas(grupo.ano, cargo=cargo, sqs=sorted(grupo.sqs)):
            return nossos, grupo
    raise parametro_invalido("cargo_sem_referencia", f"não há grupo de referência para '{cargo}'")


class _Contexto:
    """Dados compartilhados pelos candidatos dos dois lados (uma consulta por escopo)."""

    def __init__(self, repo: Repositorio, ano: int, cargo: str) -> None:
        self.repo, self.ano, self.cargo = repo, ano, cargo
        self.bases = BasesPorEscopo(repo)
        self._eleitorado: dict[str | None, pl.DataFrame] = {}

    def eleitorado(self, uf: str | None) -> pl.DataFrame:
        """Aptos e válidos por município (sem o exterior) do cargo na UF (ou Brasil)."""
        if uf not in self._eleitorado:
            linhas = self.repo.base_eleitoral(self.ano, self.cargo, por_zona=False, uf=uf)
            self._eleitorado[uf] = pl.DataFrame(
                [(b.cd_mun_ibge, b.aptos, b.validos) for b in linhas if b.cd_mun_ibge is not None],
                schema={"cd_mun_ibge": pl.Int64, "aptos": pl.Int64, "validos": pl.Int64},
                orient="row",
            )
        return self._eleitorado[uf]


def _geografia(
    ctx: _Contexto, c: Candidatura
) -> tuple[int, float | None, float | None, float | None]:
    """(n_municipios, pct_maiores, hhi, n_efetivo) pela biblioteca; exterior não tem município."""
    todos = ctx.repo.votos_territorio(ctx.ano, [c.sq_candidato], por_zona=False)
    por_mun = [(v.cd_mun_ibge, v.votos) for v in todos if v.cd_mun_ibge is not None]
    com_voto = [(cd, n) for cd, n in por_mun if n > 0]
    if not com_voto:
        return 0, None, None, None
    votos = pl.DataFrame(
        [(c.sq_candidato, cd, n) for cd, n in com_voto],
        schema={"sq_candidato": pl.Int64, "cd_mun_ibge": pl.Int64, "votos": pl.Int64},
        orient="row",
    )
    tabela = desempenho.montar_tabela(votos, ctx.eleitorado(uf_da_base(c.sg_uf)))
    linha = espacial.concentracao(tabela).row(0, named=True)
    maiores = espacial.participacao_maiores(votos).row(0, named=True)
    return (
        maiores["n_municipios_com_voto"],
        maiores["pct_maiores"],
        linha["hhi"],
        linha["n_efetivo_municipios"],
    )


def _financas(cc: ContasCand | None, votos: int) -> tuple[dict[str, float | None], dict[str, str]]:
    """Indicadores financeiros e, para cada nulo, o motivo (ausência ≠ zero)."""
    if cc is None:
        motivo = "sem prestação de contas (receitas e despesas) para o candidato nos dados"
        return dict.fromkeys(_FINANCAS), dict.fromkeys(_FINANCAS, motivo)
    valores: dict[str, float | None] = {
        "custo_voto_pago": cc.custo.custo_voto_pago,
        "receita_total": cc.receita_total,
        "receita_por_voto": cc.receita_por_voto,
        "pct_publico": cc.pct_publico,
        "pct_pessoa_fisica": cc.resumo.get("pct_pessoa_fisica"),
        "pct_autofinanciamento": cc.pct_autofinanciamento,
    }
    motivos: dict[str, str] = {}
    if valores["custo_voto_pago"] is None:
        motivos["custo_voto_pago"] = (
            "sem votos: custo por voto indefinido"
            if not votos
            else ("sem despesa lançada na prestação de contas")
        )
    sem_receita = "sem receita lançada na prestação de contas"
    for campo in (
        "receita_total", "receita_por_voto", "pct_publico", "pct_pessoa_fisica",
        "pct_autofinanciamento",
    ):  # fmt: skip
        if valores[campo] is None:
            motivos[campo] = sem_receita if cc.receita_total is None else "receita total zero"
    return valores, motivos


def _comparar(
    ctx: _Contexto,
    pares: list[tuple[Candidatura, int]],
    contas: ContasAgregadas,
    destaque: int | None,
    fotos: frozenset[tuple[int, int]],
) -> list[CandidatoComparado]:
    """Perfil de cada candidato (sem índices; entram depois, com a mediana da referência)."""
    por_sq = {cc.candidatura.sq_candidato: cc for cc in contas.por_candidato}
    entradas = [(votos, *ctx.bases.de(c)) for c, votos in pares]
    out = []
    for (c, votos), (pct, pen) in zip(pares, taxas(entradas), strict=True):
        n_mun, pct_maiores, hhi, n_ef = _geografia(ctx, c)
        fin, motivos = _financas(por_sq.get(c.sq_candidato), votos)
        motivos_geo = "sem votos em municípios"
        valores: dict[str, float | None] = {
            "votos": votos, "pct_validos": pct, "penetracao": pen,
            "n_municipios": n_mun, "pct_maiores": pct_maiores, "hhi": hhi,
            "n_efetivo_municipios": n_ef, **fin,
        }  # fmt: skip
        if hhi is None:
            motivos |= {k: motivos_geo for k in ("pct_maiores", "hhi", "n_efetivo_municipios")}
        if pct is None or pen is None:
            motivos |= {k: "sem eleitorado ou votos válidos na circunscrição"
                        for k in ("pct_validos", "penetracao") if valores[k] is None}  # fmt: skip
        out.append(
            CandidatoComparado(
                ano=c.ano,
                sq_candidato=c.sq_candidato,
                nm_urna=c.nm_urna,
                sg_uf=c.sg_uf,
                cargo=c.ds_cargo,
                partido=Partido(numero=c.nr_partido, sigla=c.sg_partido),
                resultado=c.ds_sit_tot_turno,
                votos=votos,
                destacado=c.sq_candidato == destaque,
                indicadores=Perfil(**valores),
                motivos=motivos,
                indices=None,
                **foto_e_link(fotos, ano=c.ano, sq_candidato=c.sq_candidato, uf=c.sg_uf),
            )
        )
    return out


def _quadro(candidatos: list[CandidatoComparado], cargo: str) -> pl.DataFrame:
    """Um lado como tabela da biblioteca: `cd_cargo`, `sq_candidato` e os campos do catálogo.

    O recorte já é um cargo × UF; `cd_cargo` constante só satisfaz `perfil_relativo`.
    """
    linhas = [
        {
            CD_CARGO: cargo,
            "sq_candidato": c.sq_candidato,
            **{_NO_CATALOGO.get(k, k): getattr(c.indicadores, k) for k in _COMPARAVEIS},
        }
        for c in candidatos
    ]
    esquema = {CD_CARGO: pl.String, "sq_candidato": pl.Int64} | {
        _NO_CATALOGO.get(k, k): pl.Float64 for k in _COMPARAVEIS
    }
    return pl.DataFrame(linhas, schema=esquema)


def _mediana_do_lado(
    candidatos: list[CandidatoComparado], cargo: str
) -> tuple[Perfil, dict[str, int]]:
    """Mediana por campo (`mediana_referencia`, `minimo=1`) e quantos valores a formaram.

    `minimo=1` mostra a mediana mesmo com poucos valores (os vetores da T-B20 exigem); `n_mediana`
    diz quantos foram. A spec §10.3 pede ≥ 3 valores na referência: decisão da análise.
    """
    medianas: dict[str, float | None] = dict.fromkeys(CAMPOS)
    contagem: dict[str, int] = dict.fromkeys(CAMPOS, 0)
    if candidatos:
        nomes = [_NO_CATALOGO.get(k, k) for k in _COMPARAVEIS]
        tabela = mediana_referencia(_quadro(candidatos, cargo), nomes, [CD_CARGO], minimo=1)
        por_nome = {linha["indicador"]: linha for linha in tabela.iter_rows(named=True)}
        for campo in _COMPARAVEIS:
            linha = por_nome[_NO_CATALOGO.get(campo, campo)]
            medianas[campo], contagem[campo] = linha["mediana"], linha["n"]
    return Perfil(**medianas), contagem


def _indices(
    nossos: list[CandidatoComparado], referencia: list[CandidatoComparado], cargo: str
) -> None:
    """Preenche `indices` dos nossos com `perfil_relativo` (razão, diferença em p.p. ou nulo)."""
    sem = Perfil(**dict.fromkeys(CAMPOS))
    if not nossos:
        return
    nomes = [_NO_CATALOGO.get(k, k) for k in _COMPARAVEIS]
    relativo = perfil_relativo(
        _quadro(nossos, cargo), _quadro(referencia, cargo), nomes, [CD_CARGO], minimo=1
    )
    # Campos "contexto" (votos, receita_total…) saem sem índice na spec; a API já os expõe como
    # razão nosso ÷ mediana (contrato da T-B20, usado pelo web): `razao` da biblioteca.
    relativo = relativo.with_columns(
        pl.when(pl.col("tipo") == "contexto")
        .then(razao(pl.col("valor"), pl.col("mediana_referencia")))
        .otherwise(pl.col("indice"))
        .alias("indice")
    )
    indice: dict[int, dict[str, float | None]] = {c.sq_candidato: {} for c in nossos}
    inverso = {v: k for k, v in _NO_CATALOGO.items()}
    for linha in relativo.iter_rows(named=True):
        indice[linha["sq_candidato"]][inverso.get(linha["indicador"], linha["indicador"])] = linha[
            "indice"
        ]
    for c in nossos:
        c.indices = sem.model_copy(update=indice[c.sq_candidato])


def _por_votos(pares: list[tuple[Candidatura, int]]) -> list[tuple[Candidatura, int]]:
    return sorted(pares, key=lambda p: (-p[1], p[0].sq_candidato))


def _rotulo_cargo(cargo: str, uf: str | None) -> str:
    return " · ".join([_CARGO_CURTO.get(cargo, cargo.title()), *([uf] if uf else [])])


def montar_referencias(
    repo: Repositorio, catalogo: Catalogo, *, cargo: Cargo, uf: str | None, sq: int | None
) -> Referencias:
    """Nossos × referência no cargo (e UF, quando o grupo de referência é por UF)."""
    nossos_def, ref_def = _grupo_aplicavel(repo, catalogo, cargo.value)
    por_uf = ref_def.ranking is not None
    if por_uf and uf is None:
        raise parametro_invalido("uf_obrigatoria", f"'{cargo.value}' exige o parâmetro uf")
    uf_recorte = uf if por_uf else None  # presidente é nacional: a UF pedida não filtra nada
    ano = nossos_def.ano

    nossos_cand = candidaturas_do_grupo(repo, nossos_def, uf=uf_recorte, cargo=cargo.value)
    votos_n = repo.votos_totais(ano, [c.sq_candidato for c in nossos_cand])
    pares_n = _por_votos([(c, votos_n.get(c.sq_candidato, 0)) for c in nossos_cand])
    if sq is not None and sq not in {c.sq_candidato for c, _ in pares_n}:
        raise parametro_invalido("sq_fora_dos_nossos", f"{sq} não é candidato nosso neste recorte")

    if ref_def.ranking is not None:
        assert uf_recorte is not None  # noqa: S101 - garantido acima
        pares_r = selecionar_ranking(repo, ref_def, cargo=cargo.value, uf=uf_recorte)
    else:
        cand_r = candidaturas_do_grupo(repo, ref_def, cargo=cargo.value)
        votos_r = repo.votos_totais(ano, [c.sq_candidato for c in cand_r])
        pares_r = _por_votos([(c, votos_r.get(c.sq_candidato, 0)) for c in cand_r])

    ctx, fotos = _Contexto(repo, ano, cargo.value), repo.fotos()
    contas_n = contas_de(repo, ano, [c for c, _ in pares_n])
    contas_r = contas_de(repo, ano, [c for c, _ in pares_r])
    nossos = _comparar(ctx, pares_n, contas_n, sq, fotos)
    referencia = _comparar(ctx, pares_r, contas_r, sq, fotos)

    med_ref, n_ref = _mediana_do_lado(referencia, cargo.value)
    med_nossos, n_nossos = _mediana_do_lado(nossos, cargo.value)
    _indices(nossos, referencia, cargo.value)

    rotulo_n = _rotulo_nossos(nossos_def, nossos, cargo.value, uf_recorte)
    rotulo_r = _rotulo_referencia(ref_def, len(referencia), uf_recorte)
    uf_txt = uf_recorte or ""
    vazio = (
        f"Nenhum candidato eleito de outro partido em {uf_txt} nos dados."
        if por_uf
        else "Nenhum candidato do grupo de referência nos dados."
    )
    contas_parciais = contas_n.parcial or contas_r.parcial
    return Referencias(
        ano=ano,
        cargo=cargo.value,
        uf=uf_recorte,
        rotulo=f"{rotulo_n} × {rotulo_r}",
        destaque=sq,
        nossos=Lado(
            rotulo=rotulo_n,
            grupo_id=nossos_def.id,
            candidatos=nossos,
            mediana=med_nossos,
            n_mediana=n_nossos,
            motivo_vazio=None if nossos else "Sem candidatos nossos no recorte.",
        ),
        referencia=Lado(
            rotulo=rotulo_r,
            grupo_id=ref_def.id,
            candidatos=referencia,
            mediana=med_ref,
            n_mediana=n_ref,
            motivo_vazio=None if referencia else vazio,
        ),
        contas_parciais=contas_parciais,
        base_ipca=contas_n.base_ipca or contas_r.base_ipca,
        dt_geracao=repo.dt_geracao(),
        fontes=fontes(
            ["consulta_cand", "votacao_candidato_munzona", "detalhe_votacao_munzona"]
            + (["prestacao_contas"] if contas_n.por_candidato or contas_r.por_candidato else [])
            + (["ipca"] if contas_n.base_ipca or contas_r.base_ipca else []),
            ano=ano,
            dt_geracao=repo.dt_geracao(),
        ),
    )


def _rotulo_nossos(
    grupo: DefinicaoGrupo, candidatos: list[CandidatoComparado], cargo: str, uf: str | None
) -> str:
    """Candidato único de cargo nacional: "Nome (SIGLA)"; senão "Grupo · Cargo · UF"."""
    if len(candidatos) == 1 and uf is None:
        c = candidatos[0]
        return f"{c.nm_urna} ({c.partido.sigla})"
    return f"{grupo.rotulo_curto or grupo.rotulo} · {_rotulo_cargo(cargo, uf)}"


def _rotulo_referencia(grupo: DefinicaoGrupo, n: int, uf: str | None) -> str:
    modelo = grupo.rotulo_lado or grupo.rotulo
    texto = modelo.format(n=n, uf=uf or "")
    return texto if n else f"{texto} (nenhum encontrado)"
