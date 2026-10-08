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
# O CSV chama o código TSE do município de ``CD_MUNICIPIO``.
_ORIGEM_MUN = {"cd_municipio_tse": "CD_MUNICIPIO"}
_OBRIG_ELEICAO = ("ano_eleicao", "nr_turno", "cd_eleicao", "sg_uf", "dt_geracao")

MUNICIPIO_TSE_IBGE = Contrato(
    nome="municipio_tse_ibge",
    colunas={
        "cd_uf_ibge": I8, "sg_uf": TXT, "cd_municipio_tse": I32, "nm_municipio_tse": TXT,
        "cd_mun_ibge": I32, "nm_municipio_ibge": TXT, "dt_geracao": DATA,
    },
    chave=("cd_municipio_tse",),
    nao_nulas=("cd_municipio_tse", "cd_mun_ibge", "sg_uf"),
    origem={"cd_mun_ibge": "CD_MUNICIPIO_IBGE"},
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
    origem=_ORIGEM_MUN,
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
    origem=_ORIGEM_MUN,
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
        "cd_cargo", "nr_partido", "sq_coligacao", "st_voto_em_transito",
    ),
    nao_nulas=(*_OBRIG_ELEICAO, "cd_municipio_tse", "nr_zona", "cd_cargo", "nr_partido"),
    derivadas=frozenset({"cd_mun_ibge"}),
    origem=_ORIGEM_MUN,
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
    origem=_ORIGEM_MUN,
)  # fmt: skip

# --- votação por seção → local de votação → H3 (T-D05) ---------------------------------------
# Leitura do CSV por seção (só as colunas usadas; não é publicado). Em ``sq_candidato`` o TSE
# grava -1 (branco/nulo) e -3 (legenda), que o parser transforma em nulo.
VOTACAO_SECAO = Contrato(
    nome="votacao_secao",
    colunas={
        "ano_eleicao": I16, "nr_turno": I8, "sg_uf": TXT, "cd_municipio_tse": I32,
        "nr_zona": I16, "cd_cargo": I8, "nr_votavel": I32, "qt_votos": I64,
        "nr_local_votacao": I32, "sq_candidato": I64, "dt_geracao": DATA,
    },
    chave=(),
    origem={"cd_municipio_tse": "CD_MUNICIPIO"},
)  # fmt: skip
# Chave do local de votação, comum aos três datasets abaixo. ``nr_local`` (e não
# ``nr_local_votacao``) é o nome que a API lê.
_CHAVE_LOCAL = ("nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona", "nr_local")
_COLS_LOCAL = {
    "ano_eleicao": I16, "nr_turno": I8, "sg_uf": TXT, "cd_municipio_tse": I32,
    "cd_mun_ibge": I32, "nr_zona": I16, "nr_local": I32,
}  # fmt: skip
_OBRIG_LOCAL = ("ano_eleicao", "nr_turno", "sg_uf", "cd_municipio_tse", "nr_zona", "nr_local")
# A API não filtra turno nestas tabelas: só o 1º turno é gravado (guardado pela faixa).
_TURNO_1 = {"nr_turno": (1.0, 1.0)}

# Votos nominais (candidato com SQ) por local de votação e cargo.
VOTOS_LOCAL = Contrato(
    nome="votos_local",
    colunas={**_COLS_LOCAL, "cd_cargo": I8, "sq_candidato": I64, "votos": I64, "dt_geracao": DATA},
    chave=(*_CHAVE_LOCAL, "cd_cargo", "sq_candidato"),
    nao_nulas=(*_OBRIG_LOCAL, "cd_cargo", "sq_candidato", "votos", "dt_geracao"),
    faixas=_TURNO_1,
    derivadas=frozenset({"cd_mun_ibge"}),
    origem=_ORIGEM_MUN,
)  # fmt: skip

# Totais por local e cargo: válidos = nominais + legenda; brancos e nulos à parte.
TOTAIS_LOCAL = Contrato(
    nome="totais_local",
    colunas={
        **_COLS_LOCAL, "cd_cargo": I8, "votos_nominais": I64, "votos_legenda": I64,
        "votos_brancos": I64, "votos_nulos": I64, "dt_geracao": DATA,
    },
    chave=(*_CHAVE_LOCAL, "cd_cargo"),
    nao_nulas=(*_OBRIG_LOCAL, "cd_cargo", "votos_nominais", "votos_legenda", "votos_brancos",
               "votos_nulos", "dt_geracao"),
    faixas=_TURNO_1,
    derivadas=frozenset({"cd_mun_ibge"}),
    origem=_ORIGEM_MUN,
)  # fmt: skip

# Local de votação com coordenada válida → célula H3 (ADR 0007: res 8 canônica; 7 e 6 para a
# comparação 2022×2026). ``h3`` é a res 8, nome que a API lê. Local sem coordenada fica fora.
LOCAIS_H3 = Contrato(
    nome="locais_h3",
    colunas={
        **_COLS_LOCAL, "lat": DEC, "lon": DEC, "h3": TXT, "h3_r7": TXT, "h3_r6": TXT,
        "aptos": I64, "dt_geracao": DATA,
    },
    chave=_CHAVE_LOCAL,
    nao_nulas=(*_OBRIG_LOCAL, "lat", "lon", "h3", "h3_r7", "h3_r6", "aptos"),
    faixas={**_TURNO_1, "lat": (-35.0, 6.0), "lon": (-75.0, -28.0)},
    derivadas=frozenset({"cd_mun_ibge"}),
)  # fmt: skip

CONTRATOS: dict[str, Contrato] = {
    c.nome: c
    for c in (
        MUNICIPIO_TSE_IBGE, CONSULTA_CAND, VOTACAO_CANDIDATO_MUNZONA, DETALHE_VOTACAO_MUNZONA,
        VOTACAO_PARTIDO_MUNZONA, CONSULTA_VAGAS, ELEITORADO_LOCAL_VOTACAO, VOTACAO_SECAO,
        VOTOS_LOCAL, TOTAIS_LOCAL, LOCAIS_H3,
    )
}  # fmt: skip
