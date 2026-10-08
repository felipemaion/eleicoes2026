"""Catálogo declarativo das fontes oficiais (TSE, IBGE, BCB).

Uma só fonte de verdade para URLs: o downloader apenas expande este catálogo.
Detalhes e armadilhas de cada fonte: ``docs/fontes-de-dados.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

CDN_TSE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
IBGE_API = "https://servicodados.ibge.gov.br/api/v3"
# A API v3 de malhas não traz municípios criados recentemente (Boa Esperança do Norte/MT);
# o shapefile oficial da Malha Municipal Digital 2025 traz os 5.571.
IBGE_MALHAS_MUN = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_municipais/municipio_2025/Brasil"
)
IBGE_AREAS = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/"
    "areas_territoriais/2025"
)
BCB_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

# 26 UFs + DF + ZZ (exterior), como nos arquivos por seção do TSE.
UFS: tuple[str, ...] = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ",
)  # fmt: skip

ANOS_TSE: tuple[int, ...] = (2022, 2026)


@dataclass(frozen=True)
class Fonte:
    """Fonte baixável. Os modelos aceitam ``{ano}`` e ``{uf}``."""

    id: str
    origem: str  # "tse" | "ibge" | "bcb"
    url_modelo: str
    destino_modelo: str  # relativo a data/raw
    por_ano: bool = True
    por_uf: bool = False


@dataclass(frozen=True)
class Alvo:
    """Um arquivo concreto a baixar."""

    fonte: str
    url: str
    destino: str  # relativo a data/raw


def _tse(id_: str, pasta: str, nome: str, *, por_uf: bool = False) -> Fonte:
    sufixo = "_{ano}_{uf}" if por_uf else "_{ano}"
    arquivo = f"{nome}{sufixo}.zip"
    return Fonte(
        id=id_,
        origem="tse",
        url_modelo=f"{CDN_TSE}/{pasta}/{arquivo}",
        destino_modelo=f"tse/{id_}/{arquivo}",
        por_uf=por_uf,
    )


CATALOGO: dict[str, Fonte] = {
    f.id: f
    for f in (
        _tse("consulta_cand", "consulta_cand", "consulta_cand"),
        _tse("votacao_candidato_munzona", "votacao_candidato_munzona", "votacao_candidato_munzona"),
        _tse("detalhe_votacao_munzona", "detalhe_votacao_munzona", "detalhe_votacao_munzona"),
        _tse("votacao_partido_munzona", "votacao_partido_munzona", "votacao_partido_munzona"),
        _tse("votacao_secao", "votacao_secao", "votacao_secao", por_uf=True),
        _tse("detalhe_votacao_secao", "detalhe_votacao_secao", "detalhe_votacao_secao"),
        _tse("eleitorado_local_votacao", "eleitorado_locais_votacao", "eleitorado_local_votacao"),
        _tse("consulta_vagas", "consulta_vagas", "consulta_vagas"),
        _tse("perfil_eleitorado", "perfil_eleitorado", "perfil_eleitorado"),
        _tse(
            "prestacao_contas",
            "prestacao_contas",
            "prestacao_de_contas_eleitorais_candidatos",
        ),
        Fonte(
            id="municipio_tse_ibge",
            origem="tse",
            url_modelo=f"{CDN_TSE}/municipio_tse_ibge/municipio_tse_ibge.zip",
            destino_modelo="tse/municipio_tse_ibge/municipio_tse_ibge.zip",
            por_ano=False,
        ),
        Fonte(
            id="malha_municipios",
            origem="ibge",
            url_modelo=f"{IBGE_MALHAS_MUN}/BR_Municipios_2025.zip",
            destino_modelo="ibge/BR_Municipios_2025.zip",
            por_ano=False,
        ),
        Fonte(
            id="malha_ufs",
            origem="ibge",
            url_modelo=(
                f"{IBGE_API}/malhas/paises/BR?formato=application/vnd.geo%2Bjson"
                "&intrarregiao=UF&qualidade=intermediaria"
            ),
            destino_modelo="ibge/malha_ufs.geojson",
            por_ano=False,
        ),
        Fonte(
            id="areas_ibge",
            origem="ibge",
            url_modelo=f"{IBGE_AREAS}/AR_BR_RG_UF_RGINT_RGI_MUN_2025.xls",
            destino_modelo="ibge/areas_territoriais_2025.xls",
            por_ano=False,
        ),
        Fonte(
            id="ipca",
            origem="bcb",
            url_modelo=f"{BCB_SGS}.433/dados?formato=json",
            destino_modelo="bcb/ipca_433.json",
            por_ano=False,
        ),
    )
}


def alvos(ano: int, fontes: list[str] | None = None, uf: str | None = None) -> list[Alvo]:
    """Expande o catálogo em arquivos concretos para ``ano``.

    ``fontes`` filtra por id (``None`` = todas); ``uf`` restringe as fontes por UF.
    Fontes sem ano (IBGE, BCB, crosswalk) entram sempre que selecionadas.
    """
    if ano not in ANOS_TSE:
        raise ValueError(f"ano {ano} fora do catálogo {ANOS_TSE}")
    ids = fontes if fontes else list(CATALOGO)
    desconhecidas = [i for i in ids if i not in CATALOGO]
    if desconhecidas:
        raise ValueError(f"fonte(s) desconhecida(s): {', '.join(desconhecidas)}")
    if uf is not None and uf not in UFS:
        raise ValueError(f"UF inválida: {uf}")
    saida: list[Alvo] = []
    for id_ in ids:
        fonte = CATALOGO[id_]
        ufs: tuple[str | None, ...] = ((uf,) if uf else UFS) if fonte.por_uf else (None,)
        for u in ufs:
            valores = {"ano": ano, "uf": u}
            saida.append(
                Alvo(
                    fonte=id_,
                    url=fonte.url_modelo.format(**valores),
                    destino=fonte.destino_modelo.format(**valores),
                )
            )
    return saida
