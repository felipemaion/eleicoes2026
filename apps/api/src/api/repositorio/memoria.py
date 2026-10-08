"""Implementação em memória do Repositorio, para testes de serviço."""


class RepositorioMemoria:
    """Repositorio com valores fixos."""

    def __init__(self, dt_geracao: str, anos: list[int], ufs: list[str], cargos: list[str]) -> None:
        self._dt = dt_geracao
        self._anos = anos
        self._ufs = ufs
        self._cargos = cargos

    def dt_geracao(self) -> str:
        """DT_GERACAO fixa."""
        return self._dt

    def anos(self) -> list[int]:
        """Anos fixos."""
        return list(self._anos)

    def ufs(self) -> list[str]:
        """UFs fixas."""
        return list(self._ufs)

    def cargos(self) -> list[str]:
        """Cargos fixos."""
        return list(self._cargos)

    def fechar(self) -> None:
        """Nada a liberar."""
