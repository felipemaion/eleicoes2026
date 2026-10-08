"""Contratos dos datasets TSE processados (nomes de colunas = mapa da spec, §7)."""

from __future__ import annotations

import polars as pl

from contratos.modelo import Contrato

I8, I16, I32, I64 = pl.Int8, pl.Int16, pl.Int32, pl.Int64
TXT, DEC, DATA = pl.Utf8, pl.Float64, pl.Date

# Identificação da eleição presente em toda linha de votação.
_ELEICAO = {
    "ano_eleicao": I16, "nr_turno": I8, "cd_eleicao": I32, "sg_uf": TXT,
}  # fmt: skip
_LOCAL = {
    "cd_municipio_tse": I32, "cd_mun_ibge": I32, "nr_zona": I16,
}  # fmt: skip
_OBRIG_ELEICAO = ("ano_eleicao", "nr_turno", "cd_eleicao", "sg_uf", "dt_geracao")

MUNICIPIO_TSE_IBGE = Contrato(
    nome="municipio_tse_ibge",
    colunas={
        "cd_uf_ibge": I8, "sg_uf": TXT, "cd_municipio_tse": I32, "nm_municipio_tse": TXT,
        "cd_mun_ibge": I32, "nm_municipio_ibge": TXT, "dt_geracao": DATA,
    },
    chave=("cd_municipio_tse",),
    nao_nulas=("cd_municipio_tse", "cd_mun_ibge", "sg_uf"),
    derivadas=frozenset(),
)  # fmt: skip

CONSULTA_CAND = Contrato(
    nome="consulta_cand",
    colunas={
        **_ELEICAO, "sg_ue": TXT, "nm_ue": TXT, "cd_cargo": I8, "ds_cargo": TXT,
        "sq_candidato": I64, "nr_candidato": I32, "nm_candidato": TXT, "nm_urna_candidato": TXT,
        "cd_situacao_candidatura": I8, "ds_situacao_candidatura": TXT, "tp_agremiacao": TXT,
        "nr_partido": I16, "sg_partido": TXT, "nm_partido": TXT, "nr_federacao": I16,
        "sg_federacao": TXT, "sq_coligacao": I64, "dt_nascimento": DATA, "ds_genero": TXT,
        "ds_grau_instrucao": TXT, "ds_cor_raca": TXT, "ds_ocupacao": TXT,
        "cd_sit_tot_turno": I8, "ds_sit_tot_turno": TXT, "pessoa_id": TXT, "dt_geracao": DATA,
    },
    chave=("ano_eleicao", "cd_eleicao", "nr_turno", "sq_candidato"),
    nao_nulas=(*_OBRIG_ELEICAO, "sq_candidato", "cd_cargo", "nr_partido"),
    derivadas=frozenset({"pessoa_id"}),
)  # fmt: skip

VOTACAO_CANDIDATO_MUNZONA = Contrato(
    nome="votacao_candidato_munzona",
    colunas={
        **_ELEICAO, **_LOCAL, "cd_cargo": I8, "ds_cargo": TXT, "sq_candidato": I64,
        "nr_candidato": I32, "nm_candidato": TXT, "nm_urna_candidato": TXT, "nr_partido": I16,
        "sg_partido": TXT, "nr_federacao": I16, "ds_situacao_candidatura": TXT,
        "ds_sit_tot_turno": TXT, "st_voto_em_transito": TXT, "qt_votos_nominais": I64,
        "nm_tipo_destinacao_votos": TXT, "qt_votos_nominais_validos": I64, "dt_geracao": DATA,
    },
    chave=(
        "ano_eleicao", "cd_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona",
        "cd_cargo", "sq_candidato", "st_voto_em_transito",
    ),
    nao_nulas=(*_OBRIG_ELEICAO, "cd_municipio_tse", "nr_zona", "cd_cargo", "sq_candidato",
               "qt_votos_nominais"),
    derivadas=frozenset({"cd_mun_ibge"}),
)  # fmt: skip

DETALHE_VOTACAO_MUNZONA = Contrato(
    nome="detalhe_votacao_munzona",
    colunas={
        **_ELEICAO, **_LOCAL, "cd_cargo": I8, "ds_cargo": TXT, "qt_aptos": I64,
        "qt_secoes_principais": I32, "qt_secoes_agregadas": I32, "qt_secoes_nao_instaladas": I32,
        "qt_total_secoes": I32, "qt_comparecimento": I64, "qt_eleitores_secoes_nao_instaladas": I64,
        "qt_abstencoes": I64, "st_voto_em_transito": TXT, "qt_votos": I64,
        "qt_votos_concorrentes": I64, "qt_total_votos_validos": I64,
        "qt_votos_nominais_validos": I64, "qt_total_votos_leg_validos": I64,
        "qt_votos_leg_validos": I64, "qt_votos_nom_convr_leg_validos": I64,
        "qt_total_votos_anulados": I64, "qt_votos_nominais_anulados": I64,
        "qt_votos_legenda_anulados": I64, "qt_total_votos_anul_subjud": I64,
        "qt_votos_nominais_anul_subjud": I64, "qt_votos_legenda_anul_subjud": I64,
        "qt_votos_brancos": I64, "qt_total_votos_nulos": I64, "qt_votos_nulos": I64,
        "qt_votos_nulos_tecnicos": I64, "qt_votos_anulados_apu_sep": I64, "dt_geracao": DATA,
    },
    chave=(
        "ano_eleicao", "cd_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona",
        "cd_cargo", "st_voto_em_transito",
    ),
    nao_nulas=(*_OBRIG_ELEICAO, "cd_municipio_tse", "nr_zona", "cd_cargo", "qt_aptos"),
    derivadas=frozenset({"cd_mun_ibge"}),
)  # fmt: skip

VOTACAO_PARTIDO_MUNZONA = Contrato(
    nome="votacao_partido_munzona",
    colunas={
        **_ELEICAO, **_LOCAL, "cd_cargo": I8, "ds_cargo": TXT, "tp_agremiacao": TXT,
        "nr_partido": I16, "sg_partido": TXT, "nr_federacao": I16, "sg_federacao": TXT,
        "sq_coligacao": I64, "st_voto_em_transito": TXT, "qt_votos_legenda_validos": I64,
        "qt_votos_nom_convr_leg_validos": I64, "qt_total_votos_leg_validos": I64,
        "qt_votos_nominais_validos": I64, "qt_votos_legenda_anul_subjud": I64,
        "qt_votos_nominais_anul_subjud": I64, "qt_votos_legenda_anulados": I64,
        "qt_votos_nominais_anulados": I64, "dt_geracao": DATA,
    },
    chave=(
        "ano_eleicao", "cd_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona",
        "cd_cargo", "nr_partido", "st_voto_em_transito",
    ),
    nao_nulas=(*_OBRIG_ELEICAO, "cd_municipio_tse", "nr_zona", "cd_cargo", "nr_partido"),
    derivadas=frozenset({"cd_mun_ibge"}),
)  # fmt: skip

CONSULTA_VAGAS = Contrato(
    nome="consulta_vagas",
    colunas={
        "ano_eleicao": I16, "cd_eleicao": I32, "sg_uf": TXT, "sg_ue": TXT, "cd_cargo": I8,
        "ds_cargo": TXT, "qt_vaga": I32, "dt_posse": DATA, "dt_geracao": DATA,
    },
    chave=("ano_eleicao", "cd_eleicao", "sg_ue", "cd_cargo"),
    nao_nulas=("ano_eleicao", "cd_eleicao", "sg_ue", "cd_cargo", "qt_vaga", "dt_geracao"),
)  # fmt: skip

# Uma linha por local de votação (as seções do arquivo de origem são agregadas).
ELEITORADO_LOCAL_VOTACAO = Contrato(
    nome="eleitorado_local_votacao",
    colunas={
        "aa_eleicao": I16, "nr_turno": I8, "sg_uf": TXT, **_LOCAL, "nr_local_votacao": I32,
        "nm_local_votacao": TXT, "ds_endereco": TXT, "nm_bairro": TXT,
        "nr_latitude": DEC, "nr_longitude": DEC, "qt_secoes": I32, "qt_eleitor_secao": I64,
        "dt_geracao": DATA,
    },
    chave=("aa_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona", "nr_local_votacao"),
    nao_nulas=(
        "aa_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona", "nr_local_votacao",
    ),
    faixas={"nr_latitude": (-35.0, 6.0), "nr_longitude": (-75.0, -28.0)},
    derivadas=frozenset({"cd_mun_ibge", "qt_secoes"}),
)  # fmt: skip

CONTRATOS: dict[str, Contrato] = {
    c.nome: c
    for c in (
        MUNICIPIO_TSE_IBGE, CONSULTA_CAND, VOTACAO_CANDIDATO_MUNZONA, DETALHE_VOTACAO_MUNZONA,
        VOTACAO_PARTIDO_MUNZONA, CONSULTA_VAGAS, ELEITORADO_LOCAL_VOTACAO,
    )
}  # fmt: skip
