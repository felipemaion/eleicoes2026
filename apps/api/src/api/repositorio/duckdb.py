"""Repositorio sobre DuckDB lendo Parquet; conexão em memória, arquivos só lidos."""

import json
from pathlib import Path

import duckdb

from api.repositorio.base import DadosIndisponiveis


class RepositorioDuckDB:
    """Consultas parametrizadas sobre `<dir>/*.parquet`; `<dir>/manifesto.json` dá o DT_GERACAO."""

    def __init__(self, dir_dados: Path, threads: int = 2) -> None:
        candidatos = dir_dados / "candidatos.parquet"
        manifesto = dir_dados / "manifesto.json"
        if not candidatos.is_file() or not manifesto.is_file():
            raise DadosIndisponiveis(f"candidatos.parquet/manifesto.json ausentes em {dir_dados}")
        try:
            self._dt = str(json.loads(manifesto.read_text())["dt_geracao"])
            # Somente leitura na prática: banco em memória + views sobre Parquet (nunca escrito);
            # lock_configuration impede que consultas mudem threads/limites depois.
            self._con = duckdb.connect(":memory:")
            self._con.execute("SET threads = ?", [threads])
            # DDL não aceita parâmetros; o caminho vem da configuração (nunca do usuário).
            caminho = str(candidatos).replace("'", "''")
            self._con.execute(f"CREATE VIEW candidatos AS SELECT * FROM read_parquet('{caminho}')")  # noqa: S608
            self._con.execute("SET lock_configuration = true")
        except (duckdb.Error, KeyError, ValueError) as erro:
            raise DadosIndisponiveis(str(erro)) from erro

    def threads(self) -> int:
        """Threads efetivas da conexão."""
        linha = self._con.execute("SELECT current_setting('threads')").fetchone()
        if linha is None:
            raise DadosIndisponiveis("conexão sem configuração de threads")
        return int(linha[0])

    def _coluna(self, sql: str) -> list[object]:
        # Rotas `def` rodam no threadpool: cada consulta usa um cursor próprio (conexão filha),
        # pois a conexão única não é segura para uso concorrente.
        cursor = self._con.cursor()
        try:
            return [linha[0] for linha in cursor.execute(sql).fetchall()]
        finally:
            cursor.close()

    def ping(self) -> None:
        """Prova que os dados respondem; levanta DadosIndisponiveis se não."""
        try:
            self._coluna("SELECT 1 FROM candidatos LIMIT 1")
        except duckdb.Error as erro:
            raise DadosIndisponiveis("consulta de ping falhou") from erro

    def dt_geracao(self) -> str:
        """DT_GERACAO do manifesto."""
        return self._dt

    def anos(self) -> list[int]:
        """Anos distintos."""
        return [
            int(str(a)) for a in self._coluna("SELECT DISTINCT ano FROM candidatos ORDER BY ano")
        ]

    def ufs(self) -> list[str]:
        """UFs distintas."""
        return [str(u) for u in self._coluna("SELECT DISTINCT sg_uf FROM candidatos ORDER BY 1")]

    def cargos(self) -> list[str]:
        """Cargos distintos."""
        return [str(c) for c in self._coluna("SELECT DISTINCT ds_cargo FROM candidatos ORDER BY 1")]

    def fechar(self) -> None:
        """Fecha a conexão."""
        self._con.close()
