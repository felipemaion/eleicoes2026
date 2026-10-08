"""Configuração por variáveis de ambiente (prefixo ELEICOES_); sem segredo no código."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSAO = "0.1.0"


class Settings(BaseSettings):
    """Parâmetros de execução da API."""

    model_config = SettingsConfigDict(env_prefix="ELEICOES_", env_file=".env", extra="ignore")

    dir_dados: Path = Path("data/processed")
    arquivo_grupos: Path = Path("config/grupos.yaml")
    # ADR 0002: o servidor tem pouca CPU; 2 threads é o teto.
    threads: int = 2
    cors_origens: list[str] = ["http://localhost:5173"]


@lru_cache
def obter_settings() -> Settings:
    """Settings único do processo (injetado via Depends)."""
    return Settings()
