import polars as pl
import pytest
from contratos import CONTRATOS, Contrato, ContratoViolado, validar

MINI = Contrato(
    nome="mini",
    colunas={"a": pl.Int64, "b": pl.Utf8, "c": pl.Float64},
    chave=("a",),
    nao_nulas=("a",),
    faixas={"c": (0.0, 10.0)},
)


def _df(**kw: list) -> pl.DataFrame:  # type: ignore[type-arg]
    base = {"a": [1, 2], "b": ["x", None], "c": [1.0, None]}
    base.update(kw)
    return pl.DataFrame(base, schema=MINI.schema())


def test_valido_passa() -> None:
    validar(_df(), MINI)
    validar(_df().lazy(), MINI)


def test_coluna_faltando_ou_sobrando() -> None:
    with pytest.raises(ContratoViolado, match="colunas"):
        validar(_df().drop("b"), MINI)
    with pytest.raises(ContratoViolado, match="colunas"):
        validar(_df().with_columns(z=pl.lit(1)), MINI)


def test_tipo_errado() -> None:
    with pytest.raises(ContratoViolado, match="tipo"):
        validar(_df().with_columns(pl.col("a").cast(pl.Utf8)), MINI)


def test_chave_duplicada() -> None:
    with pytest.raises(ContratoViolado, match="duplicad"):
        validar(_df(a=[1, 1]), MINI)


def test_nulo_em_coluna_obrigatoria() -> None:
    with pytest.raises(ContratoViolado, match="nulo"):
        validar(_df(a=[1, None]), MINI)


def test_fora_da_faixa() -> None:
    with pytest.raises(ContratoViolado, match="faixa"):
        validar(_df(c=[1.0, 11.0]), MINI)


def test_contratos_registrados_sem_pii() -> None:
    assert {
        "consulta_cand", "votacao_candidato_munzona", "detalhe_votacao_munzona",
        "votacao_partido_munzona", "eleitorado_local_votacao", "consulta_vagas",
        "municipio_tse_ibge",
    } <= set(CONTRATOS)  # fmt: skip
    proibidas = {"nr_cpf_candidato", "nr_titulo_eleitoral_candidato", "ds_email"}
    for c in CONTRATOS.values():
        assert not proibidas & set(c.colunas)
        assert set(c.chave) <= set(c.colunas)
        assert set(c.nao_nulas) <= set(c.colunas)


def test_nomes_seguem_o_mapa_de_colunas_da_spec() -> None:
    v = CONTRATOS["votacao_candidato_munzona"].colunas
    for col in ("sq_candidato", "qt_votos_nominais_validos", "nm_tipo_destinacao_votos", "nr_zona"):
        assert col in v
    assert "qt_aptos" in CONTRATOS["detalhe_votacao_munzona"].colunas
    assert "qt_total_votos_leg_validos" in CONTRATOS["votacao_partido_munzona"].colunas
    assert "qt_vaga" in CONTRATOS["consulta_vagas"].colunas
    assert "nr_latitude" in CONTRATOS["eleitorado_local_votacao"].colunas
