"""Gera a fixture Parquet provisória (até o contrato de T-D02). Uso: uv run python <este>."""

import json
from pathlib import Path

import duckdb

DESTINO = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        """
        COPY (SELECT * FROM (VALUES
          (2022, 1, 'SP', 'DEPUTADO FEDERAL', 30),
          (2022, 2, 'RJ', 'DEPUTADO ESTADUAL', 33),
          (2026, 3, 'SP', 'DEPUTADO FEDERAL', 14),
          (2026, 4, 'RJ', 'DEPUTADO ESTADUAL', 14)
        ) t(ano, sq_candidato, sg_uf, ds_cargo, nr_partido))
        TO ? (FORMAT PARQUET)
        """,
        [str(DESTINO / "candidatos.parquet")],
    )
    (DESTINO / "manifesto.json").write_text(
        json.dumps({"dt_geracao": "2026-10-06T12:00:00"}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
