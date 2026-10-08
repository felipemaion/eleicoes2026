"""Catálogo único de fontes oficiais: procedência de todo número que a API devolve.

Nenhuma outra parte da API monta URL de dado oficial ou de metodologia — tudo passa por
`fonte(...)`. Os endereços seguem `docs/fontes-de-dados.md` (CDN do TSE, BCB) e as âncoras
apontam para as seções de `docs/metodologia/indicadores.md` no GitHub.
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

CDN_TSE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
BCB_IPCA = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
REPO = "https://github.com/felipemaion/eleicoes2026/blob/main"
UF_GENERICA = "{UF}"  # arquivos por UF sem UF definida: o leitor troca pela sigla
METODOLOGIA = f"{REPO}/docs/metodologia/indicadores.md"


class Fonte(BaseModel):
    """De onde vem um número: arquivo oficial, momento da geração e regra aplicada."""

    dataset: str = Field(
        description="Id do dataset no catálogo (ex.: `votacao_candidato_munzona`)."
    )
    arquivo_oficial_url: str = Field(description="URL do arquivo oficial (ZIP no CDN do TSE etc.).")
    dt_geracao: str = Field(description="`DT_GERACAO` dos dados publicados pelo TSE.")
    coluna_regra: str = Field(description="Coluna(s) usada(s) e regra aplicada sobre elas.")
    metodologia_url: str = Field(description="Seção da spec que define o número (GitHub).")


@dataclass(frozen=True)
class _Entrada:
    """Linha do catálogo: URL do arquivo (aceita `{ano}`/`{uf}`), regra e âncora da spec."""

    url_modelo: str
    coluna_regra: str
    ancora: str


_CATALOGO: dict[str, _Entrada] = {
    "consulta_cand": _Entrada(
        f"{CDN_TSE}/consulta_cand/consulta_cand_{{ano}}.zip",
        "SQ_CANDIDATO, NM_URNA_CANDIDATO, DS_CARGO, NR_PARTIDO, DS_SITUACAO_CANDIDATURA, "
        "DS_SIT_TOT_TURNO: cadastro como publicado, sem CPF/título.",
        "#0-convenções-valem-para-todos-os-indicadores",
    ),
    "votacao_candidato_munzona": _Entrada(
        f"{CDN_TSE}/votacao_candidato_munzona/votacao_candidato_munzona_{{ano}}.zip",
        "QT_VOTOS_NOMINAIS_VALIDOS com NM_TIPO_DESTINACAO_VOTOS = 'Válido', somado por "
        "município (zonas e votos em trânsito somados).",
        "#21-votos-nominais",
    ),
    "detalhe_votacao_munzona": _Entrada(
        f"{CDN_TSE}/detalhe_votacao_munzona/detalhe_votacao_munzona_{{ano}}.zip",
        "QT_APTOS e QT_VOTOS_VALIDOS do cargo: denominadores de % dos válidos e penetração "
        "(‰ dos aptos).",
        "#23-penetração-métrica-âncora",
    ),
    "votacao_secao": _Entrada(
        f"{CDN_TSE}/votacao_secao/votacao_secao_{{ano}}_{{uf}}.zip",
        "QT_VOTOS por seção agregados ao local de votação e à célula H3 (só locais com "
        "coordenada).",
        "#37-agregação-em-h3",
    ),
    "prestacao_contas": _Entrada(
        f"{CDN_TSE}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{{ano}}.zip",
        "VR_RECEITA, VR_DESPESA_CONTRATADA, VR_PAGTO_DESPESA por candidato; custo por voto "
        "exclui repasses a outros candidatos/partidos.",
        "#42-custo-por-voto-contratado-e-pago-e-dívida",
    ),
    "ipca": _Entrada(
        BCB_IPCA,
        "Variação mensal do IPCA (SGS 433) para deflacionar valores de 2022 ao mês-base.",
        "#43-correção-pelo-ipca",
    ),
}


def fonte(dataset: str, *, ano: int, dt_geracao: str, uf: str | None = None) -> Fonte:
    """Bloco de procedência de um dataset do catálogo; dataset desconhecido falha alto."""
    e = _CATALOGO[dataset]
    return Fonte(
        dataset=dataset,
        arquivo_oficial_url=e.url_modelo.format(ano=ano, uf=uf or UF_GENERICA),
        dt_geracao=dt_geracao,
        coluna_regra=e.coluna_regra,
        metodologia_url=f"{METODOLOGIA}{e.ancora}",
    )


def url_dados_abertos(dataset: str, ano: int) -> str:
    """URL oficial do arquivo de dados abertos de um dataset (para os links da ficha)."""
    return _CATALOGO[dataset].url_modelo.format(ano=ano, uf=UF_GENERICA)


def fontes(datasets: list[str], *, ano: int, dt_geracao: str) -> list[Fonte]:
    """Blocos de procedência de vários datasets, na ordem pedida."""
    return [fonte(d, ano=ano, dt_geracao=dt_geracao) for d in datasets]
