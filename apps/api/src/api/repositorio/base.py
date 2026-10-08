"""Contrato de acesso a dados: serviços dependem disto, nunca do DuckDB."""

from collections.abc import Sequence
from typing import Protocol

from api.repositorio.modelos import (
    BaseEleitoral,
    Candidatura,
    CelulaH3,
    DespesaBruta,
    Municipio,
    PontoVotacao,
    ReceitaBruta,
    VariacaoIpca,
    VotosSemCoordenada,
    VotosTerritorio,
)


class DadosIndisponiveis(Exception):  # noqa: N818 - nome de domínio
    """Os dados processados não puderam ser abertos."""


class Repositorio(Protocol):
    """Leituras somente-leitura sobre os dados processados.

    Convenção de seleção de candidaturas: `partido` e `sqs` são critérios de **união**
    (partido OU lista); ambos `None` = sem restrição de grupo.
    """

    def dt_geracao(self) -> str:
        """DT_GERACAO dos dados (ISO 8601), vinda do manifesto."""
        ...

    def tp_prestacao_contas(self, ano: int) -> str:
        """`PARCIAL` ou `FINAL` para as contas do ano (manifesto); ausente = `FINAL`."""
        ...

    def anos(self) -> list[int]:
        """Anos de eleição disponíveis."""
        ...

    def ufs(self) -> list[str]:
        """UFs com candidaturas."""
        ...

    def cargos(self) -> list[str]:
        """Cargos com candidaturas."""
        ...

    def candidaturas(
        self,
        ano: int,
        *,
        uf: str | None = None,
        cargo: str | None = None,
        partido: int | None = None,
        sqs: Sequence[int] | None = None,
    ) -> list[Candidatura]:
        """Candidaturas do ano, ordenadas por (uf, cargo, nome, sq)."""
        ...

    def candidatura(self, ano: int, sq_candidato: int) -> Candidatura | None:
        """Uma candidatura ou `None`."""
        ...

    def municipios(self, codigos: Sequence[int] | None = None) -> list[Municipio]:
        """Municípios pedidos (todos se `codigos` é `None`)."""
        ...

    def votos_territorio(
        self,
        ano: int,
        sqs: Sequence[int],
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[VotosTerritorio]:
        """Σ votos dos `sqs` por município (ou município×zona); `uf`/`cd_mun_ibge` filtram."""
        ...

    def votos_totais(self, ano: int, sqs: Sequence[int]) -> dict[int, int]:
        """Votos totais por candidato (candidatos sem voto ficam fora)."""
        ...

    def base_eleitoral(
        self,
        ano: int,
        cargo: str,
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[BaseEleitoral]:
        """Aptos e válidos do cargo por município (ou município×zona); sem filtro = Brasil."""
        ...

    def votos_h3(self, ano: int, sqs: Sequence[int], *, uf: str) -> list[CelulaH3]:
        """Votos dos `sqs` e aptos por célula H3 nos municípios da UF."""
        ...

    def pontos(
        self, ano: int, sqs: Sequence[int], *, uf: str, limite: int, offset: int
    ) -> tuple[int, list[PontoVotacao]]:
        """(total de locais com voto, página) ordenados por votos desc."""
        ...

    def votos_sem_coordenada(
        self, ano: int, sqs: Sequence[int], *, uf: str, por_h3: bool
    ) -> VotosSemCoordenada:
        """Votos em locais sem lat/lon (`por_h3=False`) ou sem célula H3 (`por_h3=True`)."""
        ...

    def receitas(self, ano: int, sqs: Sequence[int]) -> list[ReceitaBruta]:
        """Receitas agregadas dos candidatos."""
        ...

    def despesas(self, ano: int, sqs: Sequence[int]) -> list[DespesaBruta]:
        """Despesas agregadas dos candidatos."""
        ...

    def ipca(self) -> list[VariacaoIpca]:
        """Série mensal de variação do IPCA."""
        ...

    def ping(self) -> None:
        """Levanta DadosIndisponiveis se os dados não respondem."""
        ...

    def fechar(self) -> None:
        """Libera a conexão."""
        ...
