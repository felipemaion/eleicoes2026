"""Linhas devolvidas pelo Repositorio: dados puros, sem regra de negócio."""

from dataclasses import dataclass
from datetime import datetime

from api.texto import nivel_relevancia


@dataclass(frozen=True)
class Candidatura:
    """Uma candidatura; `pessoa_id` (hash) liga 2022↔2026 e nunca sai pela API."""

    ano: int
    sq_candidato: int
    pessoa_id: str
    nm_urna: str
    sg_uf: str
    ds_cargo: str
    nr_partido: int
    sg_partido: str
    ds_situacao_candidatura: str | None  # 2026 chega nulo do TSE até a publicação
    ds_sit_tot_turno: str | None
    nr_candidato: int | None = None  # número de urna (busca)
    nm_civil: str | None = None  # nome civil (busca); nunca documento

    def nivel(self, termo: str) -> int:
        """Nível de relevância (0 = melhor) para o termo normalizado; ver `nivel_relevancia`."""
        return nivel_relevancia(
            self.nm_urna, self.nm_civil, self.sg_partido, self.nr_candidato, self.nr_partido, termo
        )


@dataclass(frozen=True)
class Municipio:
    """Município IBGE; `cd_amc` agrega desmembramentos (spec §5.1)."""

    cd_mun_ibge: int
    cd_amc: int
    nome: str
    uf: str
    area_km2: float | None


@dataclass(frozen=True)
class VotosTerritorio:
    """Votos de um conjunto de candidatos num território (`nr_zona` None = município).

    `cd_mun_ibge` None = voto sem município (exterior): conta no total, não tem polígono.
    """

    cd_mun_ibge: int | None
    nr_zona: int | None
    votos: int


@dataclass(frozen=True)
class BaseEleitoral:
    """Aptos e votos válidos de um cargo num território (`nr_zona` None = município).

    `cd_mun_ibge` None = exterior (sem município IBGE).
    """

    cd_mun_ibge: int | None
    nr_zona: int | None
    aptos: int
    validos: int


@dataclass(frozen=True)
class CelulaH3:
    """Votos e aptos agregados numa célula H3."""

    h3: str
    votos: int
    aptos: int


@dataclass(frozen=True)
class VotosSemCoordenada:
    """Votos do recorte em locais sem coordenada (ou sem célula H3) e o total do recorte."""

    sem_coordenada: int
    total: int


@dataclass(frozen=True)
class PontoVotacao:
    """Local de votação com votos do recorte."""

    lat: float
    lon: float
    votos: int


@dataclass(frozen=True)
class ReceitaBruta:
    """Receita agregada por candidato × (fonte, origem, natureza), rótulos do TSE."""

    sq_candidato: int
    ds_fonte_receita: str
    ds_origem_receita: str
    ds_natureza_receita: str
    valor: float
    sq_candidato_doador: int | None = None


@dataclass(frozen=True)
class DespesaBruta:
    """Despesa agregada por candidato × origem."""

    sq_candidato: int
    ds_origem_despesa: str
    contratada: float
    paga: float


@dataclass(frozen=True)
class VariacaoIpca:
    """Variação mensal do IPCA (SGS 433), `mes` = `YYYY-MM`."""

    mes: str
    variacao: float


@dataclass(frozen=True)
class ParDePessoa:
    """Candidaturas da mesma pessoa no ano `de` e no ano `para`."""

    de: Candidatura
    para: Candidatura


@dataclass(frozen=True)
class RedeDeclarada:
    """Perfil declarado ao TSE por uma candidatura (`principal` = o declarado primeiro)."""

    sq_candidato: int
    username: str
    url_tse: str
    nr_ordem: int
    principal: bool


@dataclass(frozen=True)
class SnapshotPerfil:
    """Uma coleta de um perfil; contagens nulas = perfil indisponível, nunca zero."""

    sq_candidato: int
    username: str
    status: str
    seguidores: int | None
    seguindo: int | None
    n_midias: int | None
    coletado_em: datetime  # UTC, sem fuso (o indicadores trata naïve como UTC)


@dataclass(frozen=True)
class PostRede:
    """Último estado lido de um post; curtidas nulas = ocultas pelo dono."""

    username: str
    media_id: str
    timestamp: datetime
    media_type: str
    curtidas: int | None
    comentarios: int | None
    coletado_em: datetime


@dataclass(frozen=True)
class RedesMeta:
    """Procedência dos dados de redes publicados."""

    coletado_em: datetime  # coleta mais recente (UTC)
    dt_geracao_tse: str  # DT_GERACAO do cadastro de redes do TSE
