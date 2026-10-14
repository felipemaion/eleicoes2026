"""Comparação com candidatos de referência (spec §10): catálogo, bordas e conferência aleatória.

Os vetores da spec (test_vetores_impl.py) fixam os números; aqui ficam o vínculo do catálogo
com a tabela da spec, os guardas de recorte e uma conferência contra `statistics.median`.
"""

import random
import re
import statistics
from pathlib import Path

import polars as pl
import pytest
from indicadores import referencias

SPEC = Path(__file__).resolve().parents[3] / "docs" / "metodologia" / "indicadores.md"
TIPOS_DA_SPEC = {"razão": "razao", "diferença (p.p.)": "diferenca_pp"}


def _catalogo_da_spec() -> dict[str, str]:
    secao = SPEC.read_text(encoding="utf-8").split('<a id="perfil-relativo"></a>', 1)[1]
    secao = secao.split("<a id=", 1)[0]
    linhas = re.findall(r"^\s*\| `([a-z_]+)` \| [^|]+ \| ([^|]+?) \|", secao, flags=re.M)
    return {nome: TIPOS_DA_SPEC.get(tipo, "contexto") for nome, tipo in linhas}


def test_catalogo_igual_a_tabela_da_spec() -> None:
    spec = _catalogo_da_spec()
    assert spec, "tabela do §10.3 não encontrada"
    assert dict(referencias.PERFIL) == spec
    assert list(referencias.PERFIL) == list(spec), "ordem do catálogo difere da spec"


def _ref(valores: list[float | None], uf: str = "SP", cargo: int = 6) -> pl.DataFrame:
    return pl.DataFrame(
        {"cd_cargo": [cargo] * len(valores), "sg_uf": [uf] * len(valores), "penetracao": valores},
        schema={"cd_cargo": pl.Int64, "sg_uf": pl.String, "penetracao": pl.Float64},
    )


def test_mediana_dos_nossos_com_minimo_1() -> None:
    med = referencias.mediana_referencia(_ref([4.0]), ["penetracao"], minimo=1)
    assert med.to_dicts() == [
        {"cd_cargo": 6, "sg_uf": "SP", "indicador": "penetracao", "mediana": 4.0, "n": 1}
    ]


def test_mediana_padrao_exige_tres() -> None:
    med = referencias.mediana_referencia(_ref([4.0, 6.0]), ["penetracao"])
    assert med["mediana"].to_list() == [None]
    assert med["n"].to_list() == [2]


def test_minimo_invalido() -> None:
    with pytest.raises(ValueError, match="minimo"):
        referencias.mediana_referencia(_ref([1.0]), ["penetracao"], minimo=0)


def test_entidade_coletiva_e_coluna_ausente() -> None:
    nossos = pl.DataFrame(
        {"cd_cargo": [6], "sg_uf": ["SP"], "grupo": ["missao"], "penetracao": [3.0]}
    )
    ref = _ref([2.0, 3.0, 4.0])
    df = referencias.perfil_relativo(nossos, ref, ["penetracao"], entidade="grupo")
    assert df.select("grupo", "indice").to_dicts() == [{"grupo": "missao", "indice": 1.0}]
    with pytest.raises(ValueError, match="colunas ausentes"):
        referencias.perfil_relativo(
            nossos, ref.drop("penetracao"), ["penetracao"], entidade="grupo"
        )


def test_anos_misturados_fora_do_recorte() -> None:
    ref = _ref([1.0, 2.0, 3.0]).with_columns(pl.Series("ano_eleicao", [2022, 2026, 2026]))
    nossos = _ref([1.0]).with_columns(
        pl.lit(1).alias("sq_candidato"), pl.lit(2026).alias("ano_eleicao")
    )
    with pytest.raises(ValueError, match="um ano por vez"):
        referencias.perfil_relativo(nossos, ref, ["penetracao"])
    # Com o ano no recorte, cada ano é comparado com o seu.
    df = referencias.perfil_relativo(
        nossos, ref, ["penetracao"], por=("ano_eleicao", "cd_cargo", "sg_uf")
    )
    assert df["n_referencia"].to_list() == [2]


def test_selecao_sem_nenhum_totalizado_devolve_vazio_tipado() -> None:
    candidatos = pl.DataFrame(
        {
            "cd_cargo": [6, 6],
            "sg_uf": ["SP", "SP"],
            "sq_candidato": [1, 2],
            "nr_partido": [13, 22],
            "ds_sit_tot_turno": [None, None],
            "votos": [10, 20],
        },
        schema_overrides={"ds_sit_tot_turno": pl.String},
    )
    df = referencias.selecionar_eleitos(candidatos)
    assert df.height == 0
    assert df.columns == ["cd_cargo", "sg_uf", "posicao", "sq_candidato", "nr_partido", "votos"]


def test_n_invalido() -> None:
    with pytest.raises(ValueError, match="n deve"):
        referencias.selecionar_eleitos(pl.DataFrame(), n=0)


@pytest.mark.parametrize("semente", range(5))
def test_indice_confere_com_statistics_median(semente: int) -> None:
    rng = random.Random(semente)  # noqa: S311 - dados sintéticos de teste
    valores: list[float | None] = [
        None if rng.random() < 0.2 else rng.uniform(0, 100) for _ in range(rng.randint(3, 9))
    ]
    nosso = rng.uniform(0, 100)
    nossos = _ref([nosso]).with_columns(pl.lit(7).alias("sq_candidato"))
    df = referencias.perfil_relativo(nossos, _ref(valores), ["penetracao"])
    validos = [v for v in valores if v is not None]
    esperado = statistics.median(validos) if len(validos) >= 3 else None
    linha = df.row(0, named=True)
    assert linha["n_referencia"] == len(validos)
    if esperado is None:
        assert linha["mediana_referencia"] is None
        assert linha["indice"] is None
    else:
        assert linha["mediana_referencia"] == pytest.approx(esperado)
        assert linha["indice"] == pytest.approx(nosso / esperado)
