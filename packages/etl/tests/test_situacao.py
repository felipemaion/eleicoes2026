"""`foi_as_urnas`: candidatura que constou na urna (T-D11, docs/fontes-de-dados.md)."""

import polars as pl
from etl.situacao import foi_as_urnas


def test_regra_cobre_substituido_cancelado_indeferido_com_recurso_e_apto() -> None:
    cand = pl.DataFrame(
        {
            "caso": [
                "apto eleito",
                "apto sem voto",
                "substituido",
                "cancelado",
                "indeferido c/ voto",
            ],
            "ds_situacao_candidatura": ["APTO", "APTO", None, "INAPTO", "INAPTO"],
            # resultado do turno só existe para quem constou na urna
            "cd_sit_tot_turno": [2, 4, None, None, 4],
            "ds_sit_tot_turno": ["ELEITO", "NÃO ELEITO", None, None, "NÃO ELEITO"],
        },
        schema_overrides={"cd_sit_tot_turno": pl.Int8},
    )
    r = cand.with_columns(foi_as_urnas().alias("f"))
    assert dict(zip(r["caso"], r["f"], strict=True)) == {
        "apto eleito": True,
        "apto sem voto": True,
        "substituido": False,
        "cancelado": False,
        "indeferido c/ voto": True,
    }
