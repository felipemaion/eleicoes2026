"""Links oficiais (TSE) de uma candidatura, montados a partir de padrões documentados.

`verificado = True` só para o que foi aberto no navegador e funcionou (T-B08, 2026-10-08);
o resto sai com `verificado = False` e uma nota dizendo o que conferir, nunca um link
"garantido" sem prova. URLs de arquivos de dados abertos vêm do catálogo (`fontes`).
"""

from typing import Literal

from pydantic import BaseModel, Field

from api.dominio import Cargo
from api.fontes import url_dados_abertos

DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga"
RESULTADOS = "https://resultados.tse.jus.br/oficial/app/index.html"
ESTATISTICAS_TSE = "https://www.tse.jus.br/eleicoes/estatisticas/estatisticas-eleitorais"
# Id da eleição no DivulgaCandContas (`/rest/v1/eleicao/ordinarias`, conferido em 2026-10-08).
ELEICAO_DIVULGA = {2026: 20322002026, 2022: 2040602022}
# `CD_ELEICAO` do TSE em 2026: pres./senador/dep. federal vs. governador/dep. estadual/distrital.
ELEICAO_RESULTADOS_2026 = {"federal": 6257, "estadual": 6259}
_CARGOS_FEDERAIS = {Cargo.PRESIDENTE, Cargo.SENADOR, Cargo.DEPUTADO_FEDERAL}

TipoLink = Literal[
    "votos_oficiais",
    "divulgacand_lista",
    "divulgacand_candidato",
    "divulgacand_ficha_json",
    "dados_abertos_votos",
    "dados_abertos_contas",
]


class Link(BaseModel):
    """Um link oficial, com a honestidade de dizer se foi conferido."""

    tipo: TipoLink
    rotulo: str
    url: str
    verificado: bool = Field(description="true = aberto e conferido; false = padrão a conferir.")
    nota: str | None = Field(description="Obrigatória quando `verificado = false`.")


def _votos_oficiais(ano: int, uf: str, cargo: Cargo) -> Link:
    if ano != 2026:
        return Link(
            tipo="votos_oficiais",
            rotulo="Estatísticas e resultados do TSE",
            url=ESTATISTICAS_TSE,
            verificado=False,
            nota="O app de resultados do TSE só traz a eleição corrente; para 2022 use o "
            "arquivo de dados abertos de votação (link abaixo) ou esta página de estatísticas.",
        )
    federal = cargo in _CARGOS_FEDERAIS
    cd = ELEICAO_RESULTADOS_2026["federal" if federal else "estadual"]
    return Link(
        tipo="votos_oficiais",
        rotulo="Votação oficial do cargo na UF (TSE)",
        url=(
            f"{RESULTADOS}#/eleicao/{cd}/uf/{uf.lower()}/cargo/{cargo.codigo}/vis/nominal/resultados"
        ),
        verificado=True,
        nota="Página do cargo na UF; o app do TSE não tem URL por candidato — procure o "
        "nome na lista.",
    )


def _divulgacand(ano: int, sq_candidato: int, uf: str) -> list[Link]:
    eleicao = ELEICAO_DIVULGA[ano]
    return [
        Link(
            tipo="divulgacand_lista",
            rotulo="Candidaturas no DivulgaCandContas",
            url=f"{DIVULGA}/#/candidato/{uf}/{uf}/{eleicao}",
            verificado=uf == "BR",
            nota=None
            if uf == "BR"
            else "Lista de candidaturas da UF (escolha o cargo e abra o candidato); "
            "padrão conferido só para BR.",
        ),
        Link(
            tipo="divulgacand_candidato",
            rotulo="Perfil, bens e prestação de contas (DivulgaCandContas)",
            url=f"{DIVULGA}/#/candidato/{ano}/{eleicao}/{uf}/{sq_candidato}",
            verificado=False,
            nota="Padrão público do DivulgaCandContas; no teste automatizado a página não "
            "carregou (a SPA do TSE respondeu erro), então confira abrindo o link. "
            "Alternativa: o link de candidaturas.",
        ),
        Link(
            tipo="divulgacand_ficha_json",
            rotulo="Ficha oficial em JSON (DivulgaCandContas)",
            url=(
                f"{DIVULGA}/rest/v1/candidatura/buscar/{ano}/{uf}/{eleicao}"
                f"/candidato/{sq_candidato}"
            ),
            verificado=True,
            nota="Abra no navegador (o TSE bloqueia scripts); traz cargo, partido, bens e "
            "situação do candidato.",
        ),
    ]


def links_da_candidatura(*, ano: int, sq_candidato: int, uf: str, cargo: str) -> list[Link]:
    """Links oficiais de uma candidatura (`uf = BR` para presidente)."""
    return [
        _votos_oficiais(ano, uf, Cargo(cargo.upper())),
        *_divulgacand(ano, sq_candidato, uf),
        Link(
            tipo="dados_abertos_votos",
            rotulo="Arquivo de dados abertos: votação por candidato",
            url=url_dados_abertos("votacao_candidato_munzona", ano),
            verificado=True,
            nota=None,
        ),
        Link(
            tipo="dados_abertos_contas",
            rotulo="Arquivo de dados abertos: prestação de contas",
            url=url_dados_abertos("prestacao_contas", ano),
            verificado=True,
            nota=None,
        ),
    ]
