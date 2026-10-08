"""Configuração por variáveis de ambiente (prefixo ELEICOES_); sem segredo no código."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSAO = "0.1.0"
# Raiz do repositório (apps/api/src/api/config.py → 4 níveis acima); em produção use env absoluto.
RAIZ = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Parâmetros de execução da API."""

    model_config = SettingsConfigDict(env_prefix="ELEICOES_", env_file=".env", extra="ignore")

    dir_dados: Path = RAIZ / "data" / "processed"
    arquivo_grupos: Path = RAIZ / "config" / "grupos.yaml"
    # Base dos caminhos relativos de `criterio.lista.arquivo` em grupos.yaml.
    raiz_repositorio: Path = RAIZ
    # Cache-Control: o dado muda no máximo diariamente; a revalidação por ETag cobre o resto.
    cache_max_age: int = 300
    # Entradas do cache LRU dos serviços (mapa nacional, comparativos…).
    cache_capacidade: int = 256
    # ADR 0002: o servidor tem pouca CPU; 2 threads é o teto.
    # `ELEICOES_DUCKDB_THREADS` é o nome que o compose de produção (Oracle) usa.
    threads: int = Field(
        default=2,
        validation_alias=AliasChoices("ELEICOES_DUCKDB_THREADS", "ELEICOES_THREADS", "threads"),
    )
    # Limites do DuckDB (revisão de segurança): memória e temporários têm teto, pois o contêiner
    # tem 2 GB e a raiz é read-only (`/tmp` é tmpfs gravável de 512 MB no compose).
    duck_memory_limit: str = "1200MB"
    duck_max_temp_directory_size: str = "400MB"
    duck_temp_directory: Path = Path("/tmp/duck")  # noqa: S108 - tmpfs do contêiner
    # Cálculos pesados simultâneos; o excedente recebe 503 + Retry-After.
    calculos_simultaneos: int = 4
    cors_origens: list[str] = ["http://localhost:5173"]


@lru_cache
def obter_settings() -> Settings:
    """Settings único do processo (injetado via Depends)."""
    return Settings()
