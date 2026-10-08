"""Contrato de acesso a dados: serviços dependem disto, nunca do DuckDB."""

from typing import Protocol


class DadosIndisponiveis(Exception):  # noqa: N818 - nome de domínio
    """Os dados processados não puderam ser abertos."""


class Repositorio(Protocol):
    """Leituras somente-leitura sobre os dados processados."""

    def dt_geracao(self) -> str:
        """DT_GERACAO dos dados (ISO 8601), vinda do manifesto."""
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

    def ping(self) -> None:
        """Levanta DadosIndisponiveis se os dados não respondem."""
        ...

    def fechar(self) -> None:
        """Libera a conexão."""
        ...
