"""Imprime o OpenAPI (`make openapi`); não precisa de dados."""

import json
import sys

from api.config import Settings
from api.main import criar_app


def main() -> None:
    """Gera o esquema sem abrir o lifespan."""
    app = criar_app(Settings(versao_app="openapi"))
    sys.stdout.write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
