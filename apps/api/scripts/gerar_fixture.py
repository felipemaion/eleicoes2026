"""Gera as fixtures Parquet de teste no layout real do ETL (contratos de T-D02, PR #29).

Datasets com contrato (`packages/contratos/.../tse.py`) saem em
`<dest>/<dataset>/ano=AAAA/<dataset>.parquet` com os nomes de coluna do TSE em minúsculas
(só a projeção que a API lê). O que ainda não tem contrato (área/AMC do município, H3 e votos por
local de votação) sai provisório em `<dest>/<nome>.parquet`.

Mundo pequeno, conferível à mão:

* 2026 Dep. Federal SP — Missão (14): sq 3 (1000 votos, receitas/despesas do vetor da spec),
  sq 5 (180 votos); sq 7 (PP, entra em mbl_2026 pela lista) e sq 6 (outro partido).
* 2022 Dep. Federal SP — MBL 2022: sq 1 (=pessoa A, sq 3 em 2026), sq 8,
  sq 9 (=pessoa D, sq 7 em 2026). sq 10 é do nº 14 em 2022 (PTB): não pertence à Missão.
* Dep. Estadual RJ: sq 2 (2022) e sq 4 (2026), mesma pessoa C.

Uso: uv run python apps/api/scripts/gerar_fixture.py
"""

import json
import shutil
from datetime import date
from pathlib import Path

import duckdb

DESTINO = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
# Caixa do ETL real (T-B03): "Deputado Federal"; a API normaliza para o enum em maiúsculas.
DF, DE, PR = "Deputado Federal", "Deputado Estadual", "Presidente"
SP, CAMP, SANTOS, RIO = 3550308, 3509502, 3548500, 3304557

TABELAS: dict[str, tuple[str, list[tuple[object, ...]]]] = {
    "candidatos": (
        "ano, sq_candidato, pessoa_id, nm_urna, sg_uf, ds_cargo, nr_partido, sg_partido,"
        " ds_situacao_candidatura, ds_sit_tot_turno",
        [
            (2022, 1, "pA", "A 2022", "SP", DF, 30, "NOVO", "APTO", "SUPLENTE"),
            (2022, 2, "pC", "C 2022", "RJ", DE, 33, "PMN", "APTO", "NÃO ELEITO"),
            (2022, 8, "pE", "E 2022", "SP", DF, 44, "UNIÃO", "APTO", "ELEITO POR QP"),
            (2022, 9, "pD", "D 2022", "SP", DF, 44, "UNIÃO", "APTO", "NÃO ELEITO"),
            (2022, 10, "pG", "G 2022", "SP", DF, 14, "PTB", "APTO", "NÃO ELEITO"),
            (2026, 3, "pA", "A", "SP", DF, 14, "MISSÃO", "APTO", "SUPLENTE"),
            (2026, 4, "pC", "C", "RJ", DE, 14, "MISSÃO", "APTO", "NÃO ELEITO"),
            (2026, 5, "pB", "B", "SP", DF, 14, "MISSÃO", "APTO", "NÃO ELEITO"),
            (2026, 6, "pF", "F", "SP", DF, 15, "MDB", "APTO", "ELEITO POR MÉDIA"),
            (2026, 7, "pD", "D", "SP", DF, 11, "PP", "APTO", "ELEITO POR QP"),
            # Presidente: o TSE grava a candidatura com sg_uf = BR (arquivo BR.parquet).
            (2026, 11, "pP", "P", "BR", PR, 30, "NOVO", "APTO", "2º TURNO"),
        ],
    ),
    "municipios": (
        "cd_mun_ibge, cd_amc, nome, uf, area_km2",
        [
            (SP, SP, "São Paulo", "SP", 1521.11),
            (CAMP, CAMP, "Campinas", "SP", 794.57),
            (SANTOS, SANTOS, "Santos", "SP", 280.67),
            (RIO, RIO, "Rio de Janeiro", "RJ", 1200.33),
        ],
    ),
    "eleitorado_munzona": (
        "ano, sg_uf, ds_cargo, cd_mun_ibge, nr_zona, aptos, votos_validos",
        [
            (2026, "SP", DF, SP, 1, 10000, 7000),
            (2026, "SP", DF, SP, 2, 5000, 3500),
            (2026, "SP", DF, CAMP, 1, 2000, 1500),
            (2026, "SP", DF, SANTOS, 1, 500, 400),
            (2022, "SP", DF, SP, 1, 9000, 6500),
            (2022, "SP", DF, SP, 2, 5000, 3500),
            (2022, "SP", DF, CAMP, 1, 2000, 1600),
            (2022, "SP", DF, SANTOS, 1, 500, 400),
            (2026, "RJ", DE, RIO, 1, 8000, 5600),
            (2022, "RJ", DE, RIO, 1, 8000, 5800),
            # Presidente (Brasil): base por UF e o exterior (ZZ), que não tem município IBGE.
            (2026, "SP", PR, SP, 1, 10000, 7000),
            (2026, "SP", PR, SP, 2, 5000, 3500),
            (2026, "SP", PR, CAMP, 1, 2000, 1500),
            (2026, "SP", PR, SANTOS, 1, 500, 400),
            (2026, "RJ", PR, RIO, 1, 8000, 5600),
            (2026, "ZZ", PR, None, 1, 300, 250),
        ],
    ),
    "votos_munzona": (
        "ano, sq_candidato, cd_mun_ibge, nr_zona, votos",
        [
            (2026, 3, SP, 1, 700),
            (2026, 3, SP, 2, 300),
            (2026, 5, SP, 1, 100),
            (2026, 5, CAMP, 1, 40),
            (2026, 5, SANTOS, 1, 40),
            (2026, 7, SP, 1, 500),
            (2026, 7, CAMP, 1, 200),
            (2026, 6, SP, 1, 2000),
            # Presidente sq 11: votos no exterior chegam sem município IBGE (T-B07).
            (2026, 11, SP, 1, 3000),
            (2026, 11, CAMP, 1, 500),
            (2026, 11, None, 1, 200),
            (2026, 4, RIO, 1, 400),
            (2022, 1, SP, 1, 500),
            (2022, 1, SP, 2, 200),
            (2022, 1, CAMP, 1, 100),
            (2022, 8, SP, 1, 300),
            (2022, 9, CAMP, 1, 60),
            (2022, 10, SP, 1, 50),
            (2022, 2, RIO, 1, 300),
        ],
    ),
    "locais_votacao": (
        "ano, cd_mun_ibge, nr_zona, nr_local, lat, lon, h3, aptos",
        [
            (2026, SP, 1, 1001, -23.55, -46.63, "88a81000a1fffff", 6000),
            (2026, SP, 1, 1002, -23.56, -46.64, "88a81000a1fffff", 4000),
            (2026, SP, 2, 2001, -23.60, -46.70, "88a81000e5fffff", 5000),
            (2026, CAMP, 1, 3001, -22.90, -47.06, "88a8100e61fffff", 2000),
            (2026, SANTOS, 1, 4001, -23.96, -46.33, "88a8100b13fffff", 500),
            # Sem coordenada (como no TSE real): fora dos pontos e do H3, mas com voto (T-B06).
            (2026, SP, 3, 5001, None, None, None, 1000),
        ],
    ),
    "votos_local": (
        "ano, sq_candidato, cd_mun_ibge, nr_zona, nr_local, votos",
        [
            (2026, 3, SP, 1, 1001, 450),
            (2026, 3, SP, 1, 1002, 250),
            (2026, 3, SP, 2, 2001, 300),
            (2026, 5, SP, 1, 1001, 100),
            (2026, 5, CAMP, 1, 3001, 40),
            (2026, 5, SANTOS, 1, 4001, 40),
            (2026, 3, SP, 3, 5001, 120),
            (2026, 7, SP, 1, 1001, 300),
            (2026, 7, SP, 1, 1002, 200),
            (2026, 7, CAMP, 1, 3001, 200),
            (2026, 11, SP, 1, 1001, 2000),
            (2026, 11, SP, 1, 1002, 1000),
            (2026, 11, CAMP, 1, 3001, 500),
        ],
    ),
    "receitas": (
        "ano, sq_candidato, ds_fonte_receita, ds_origem_receita, ds_natureza_receita, vr_receita",
        [
            # sq 3 = caso c1_todas_as_categorias de vetores/receitas.json (c1 → 3)
            (2026, 3, "FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO", 50000.0),
            (2026, 3, "FUNDO PARTIDARIO", "Recursos de partido político", "FINANCEIRO", 10000.0),
            (2026, 3, "OUTROS RECURSOS", "Recursos de pessoas físicas", "FINANCEIRO", 15000.0),
            (2026, 3, "OUTROS RECURSOS", "Recursos próprios", "FINANCEIRO", 5000.0),
            (
                2026,
                3,
                "OUTROS RECURSOS",
                "Recursos de Financiamento Coletivo",
                "FINANCEIRO",
                8000.0,
            ),
            (2026, 3, "OUTROS RECURSOS", "Recursos de pessoas físicas", "ESTIMÁVEL", 2000.0),
            (2026, 3, "OUTROS RECURSOS", "Recursos de outros candidatos", "FINANCEIRO", 7000.0),
            (
                2026,
                3,
                "OUTROS RECURSOS",
                "Rendimentos de aplicações financeiras",
                "FINANCEIRO",
                3000.0,
            ),
            (2026, 5, "FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO", 20000.0),
            (2026, 5, "OUTROS RECURSOS", "Recursos próprios", "FINANCEIRO", 5000.0),
            (2026, 4, "FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO", 3000.0),
            (2022, 1, "FUNDO ESPECIAL", "Recursos de partido político", "FINANCEIRO", 30000.0),
            (2022, 1, "OUTROS RECURSOS", "Recursos próprios", "FINANCEIRO", 10000.0),
        ],
    ),
    "despesas": (
        "ano, sq_candidato, ds_origem_despesa, vr_despesa_contratada, vr_despesa_paga",
        [
            # sq 3 = c1 do vetor custo_por_voto (100000 contratada / 80000 paga / 1000 votos)
            (2026, 3, "Publicidade por materiais impressos", 100000.0, 80000.0),
            (2026, 3, "Doações financeiras a outros candidatos/partidos", 400.0, 400.0),
            (2026, 5, "Publicidade por materiais impressos", 5000.0, 5000.0),
            (2026, 4, "Serviços de terceiros", 2000.0, 2000.0),
            (2022, 1, "Publicidade por materiais impressos", 40000.0, 40000.0),
        ],
    ),
}

# IPCA mensal constante (0,5 %) out/2022→set/2026 — fator = 1,005^48, trivial de conferir.
IPCA = [(f"{2022 + (9 + i) // 12}-{(9 + i) % 12 + 1:02d}", 0.5) for i in range(48)]


DT = date(2026, 10, 6)
CD_ELEICAO = {2022: 546, 2026: 6259}
TXT, INT, DBL, DAT = "VARCHAR", "BIGINT", "DOUBLE", "DATE"


def _tse(mun: int | None) -> int:
    """Código TSE fictício do município (a API só usa o IBGE); exterior (`None`) = 0."""
    return 0 if mun is None else mun // 10


# Nome civil e número de urna por candidato (consulta_cand real traz os dois; busca, T-B07).
NOME_CIVIL = {
    1: "ANA ALVES DA SILVA", 2: "CARLOS CÉSAR RAMOS", 3: "ANA ALVES DA SILVA",
    4: "CARLOS CÉSAR RAMOS", 5: "BRUNO BARBOSA LIMA", 6: "FÁBIO FERREIRA", 7: "DANIEL DIAS",
    8: "EDUARDO ESTÊVÃO", 9: "DANIEL DIAS", 10: "GUSTAVO GOMES", 11: "PAULO PEREIRA",
}  # fmt: skip
NUMERO = {1: 1414, 2: 33123, 3: 1415, 4: 14001, 5: 14002, 6: 1500, 7: 1100, 8: 4400,
          9: 4401, 10: 1416, 11: 30}  # fmt: skip


def _real() -> dict[str, tuple[dict[str, str], list[tuple[object, ...]]]]:
    """Expande o mundo simplificado nos datasets com contrato (nomes reais do TSE)."""
    cand = {c[1]: c for c in TABELAS["candidatos"][1] if c[0] in (2022, 2026)}
    uf_de: dict[int | None, str] = {m[0]: m[3] for m in TABELAS["municipios"][1]}
    uf_de[None] = "ZZ"  # exterior
    nome_de = {m[0]: m[2] for m in TABELAS["municipios"][1]}
    uf_de_cand = {c[1]: c[4] for c in TABELAS["candidatos"][1]}
    cands = [
        (a, 1, CD_ELEICAO[a], uf, cargo, sq, NUMERO[sq], NOME_CIVIL[sq], nm, parte, sg, sit, res,
         pessoa, DT)
        for (a, sq, pessoa, nm, uf, cargo, parte, sg, sit, res) in TABELAS["candidatos"][1]
    ]
    votos = []
    for a, sq, mun, zona, n in TABELAS["votos_munzona"][1]:
        cargo = cand[sq][5]
        # Parte dos votos de sq 3 chega como "voto em trânsito": a API soma os dois (spec §2.1).
        partes = (
            [("N", n - 50), ("S", 50)] if (a, sq, mun, zona) == (2026, 3, SP, 1) else [("N", n)]
        )
        votos += [
            (a, 1, uf_de[mun], _tse(mun), mun, zona, cargo, sq, st, v, v, DT) for st, v in partes
        ]
    detalhe = [
        (a, 1, uf, _tse(mun), mun, zona, cargo, "N", apt, val, DT)
        for a, uf, cargo, mun, zona, apt, val in TABELAS["eleitorado_munzona"][1]
    ]
    locais = [
        (a, 1, uf_de[mun], _tse(mun), mun, zona, nl, lat, lon, apt, DT)
        for a, mun, zona, nl, lat, lon, _h3, apt in TABELAS["locais_votacao"][1]
    ]
    muns = [
        (35 if uf == "SP" else 33, uf, _tse(m), nome_de[m], m, nome_de[m], DT)
        for m, uf in uf_de.items()
        if m is not None
    ]
    return {
        "consulta_cand": (
            dict(
                ano_eleicao=INT, nr_turno=INT, cd_eleicao=INT, sg_uf=TXT, ds_cargo=TXT,
                sq_candidato=INT, nr_candidato=INT, nm_candidato=TXT, nm_urna_candidato=TXT,
                nr_partido=INT, sg_partido=TXT, ds_situacao_candidatura=TXT,
                ds_sit_tot_turno=TXT, pessoa_id=TXT, dt_geracao=DAT,
            ),
            cands,
        ),
        "votacao_candidato_munzona": (
            dict(
                ano_eleicao=INT, nr_turno=INT, sg_uf=TXT, cd_municipio_tse=INT, cd_mun_ibge=INT,
                nr_zona=INT, ds_cargo=TXT, sq_candidato=INT, st_voto_em_transito=TXT,
                qt_votos_nominais=INT, qt_votos_nominais_validos=INT, dt_geracao=DAT,
            ),
            votos,
        ),
        "detalhe_votacao_munzona": (
            dict(
                ano_eleicao=INT, nr_turno=INT, sg_uf=TXT, cd_municipio_tse=INT, cd_mun_ibge=INT,
                nr_zona=INT, ds_cargo=TXT, st_voto_em_transito=TXT, qt_aptos=INT,
                qt_total_votos_validos=INT, dt_geracao=DAT,
            ),
            detalhe,
        ),
        "eleitorado_local_votacao": (
            dict(
                aa_eleicao=INT, nr_turno=INT, sg_uf=TXT, cd_municipio_tse=INT, cd_mun_ibge=INT,
                nr_zona=INT, nr_local_votacao=INT, nr_latitude=DBL, nr_longitude=DBL,
                qt_eleitor_secao=INT, dt_geracao=DAT,
            ),
            locais,
        ),
        "municipio_tse_ibge": (
            dict(
                cd_uf_ibge=INT, sg_uf=TXT, cd_municipio_tse=INT, nm_municipio_tse=TXT,
                cd_mun_ibge=INT, nm_municipio_ibge=TXT, dt_geracao=DAT,
            ),
            muns,
        ),
        # Prestação de contas: um registro por candidato × rótulo, como o ETL grava. O doador
        # (transferência entre candidatos) é coluna extra opcional: o TSE agregado não a traz.
        "receitas_candidatos": (
            dict(
                ano_eleicao=INT, nr_turno=INT, sg_uf=TXT, tp_prestacao_contas=TXT,
                sq_candidato=INT, ds_fonte_receita=TXT, ds_origem_receita=TXT,
                ds_natureza_receita=TXT, vr_receita=DBL, sq_candidato_doador=INT, dt_geracao=DAT,
            ),
            [
                (a, 1, uf_de_cand[sq], "FINAL", sq, f, o, n, v,
                 5 if o == "Recursos de outros candidatos" else None, DT)
                for a, sq, f, o, n, v in TABELAS["receitas"][1]
            ]
            # Linha "sem movimento" do ETL real: fonte e origem nulas, valor 0 (~2,5 mil por ano).
            + [(2026, 1, "SP", "FINAL", 5, None, None, "FINANCEIRO", 0.0, None, DT)],
        ),
        "despesas_contratadas_candidatos": (
            dict(
                ano_eleicao=INT, nr_turno=INT, sg_uf=TXT, tp_prestacao_contas=TXT,
                sq_candidato=INT, ds_origem_despesa=TXT, vr_despesa_contratada=DBL, dt_geracao=DAT,
            ),
            [
                (a, 1, uf_de_cand[sq], "Final", sq, o, c, DT)
                for a, sq, o, c, _p in TABELAS["despesas"][1]
            ]
            # O ETL real traz linhas "sem movimento": origem nula e valor 0 (≈ 5 mil por ano).
            + [(2026, 1, "SP", "Final", 5, None, 0.0, DT)],
        ),
        "despesas_pagas_candidatos": (
            dict(
                ano_eleicao=INT, nr_turno=INT, sg_uf=TXT, tp_prestacao_contas=TXT,
                sq_candidato=INT, ds_fonte_despesa=TXT, ds_origem_despesa=TXT,
                vr_pagto_despesa=DBL, dt_geracao=DAT,
            ),
            [
                (a, 1, uf_de_cand[sq], "Final", sq, "Fundo Especial de Financiamento de Campanha",
                 o, p, DT)
                for a, sq, o, _c, p in TABELAS["despesas"][1]
            ],
        ),
    }  # fmt: skip


def _provisorio() -> dict[str, tuple[dict[str, str], list[tuple[object, ...]]]]:
    """Datasets sem contrato ainda (pedir ao `dados`): formato flat com `ano` quando cabe."""
    extra = [(m[0], m[1], m[4]) for m in TABELAS["municipios"][1]]
    h3 = [(a, m, z, nl, h) for a, m, z, nl, _la, _lo, h, _ap in TABELAS["locais_votacao"][1]]
    return {
        "municipios_extra": (dict(cd_mun_ibge=INT, cd_amc=INT, area_km2=DBL), extra),
        "locais_h3": (dict(ano=INT, cd_mun_ibge=INT, nr_zona=INT, nr_local=INT, h3=TXT), h3),
        "votos_local": (
            dict(ano=INT, sq_candidato=INT, cd_mun_ibge=INT, nr_zona=INT, nr_local=INT, votos=INT),
            TABELAS["votos_local"][1],
        ),
        "ipca": (dict(mes=TXT, variacao=DBL), [(m, v) for m, v in IPCA]),
    }  # fmt: skip


def _escrever(
    con: duckdb.DuckDBPyConnection,
    nome: str,
    colunas: dict[str, str],
    linhas: list[tuple[object, ...]],
    destino: Path,
) -> None:
    ddl = ", ".join(f"{c} {t}" for c, t in colunas.items())
    con.execute(f"CREATE OR REPLACE TABLE {nome}({ddl})")
    con.executemany(f"INSERT INTO {nome} VALUES ({', '.join('?' * len(colunas))})", linhas)  # noqa: S608
    destino.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY {nome} TO ? (FORMAT PARQUET)", [str(destino)])


def main() -> None:
    """Recria tests/fixtures: datasets em hive, provisórios flat e manifesto."""
    if DESTINO.exists():
        for item in DESTINO.iterdir():
            if item.suffix == ".parquet":
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    con = duckdb.connect()
    for nome, (colunas, linhas) in _real().items():
        coluna_ano = "aa_eleicao" if nome == "eleitorado_local_votacao" else "ano_eleicao"
        posicao = list(colunas).index(coluna_ano) if nome != "municipio_tse_ibge" else None
        grupos: dict[object, list[tuple[object, ...]]] = {}
        for linha in linhas:
            grupos.setdefault(linha[posicao] if posicao is not None else 2026, []).append(linha)
        for ano, parte in grupos.items():
            destino = DESTINO / nome / f"ano={ano}" / f"{nome}.parquet"
            _escrever(con, nome, colunas, parte, destino)
    for nome, (colunas, linhas) in _provisorio().items():
        # IPCA: o ETL grava `ipca/ipca.parquet` (diretório, sem partição de ano).
        destino = (
            DESTINO / nome / f"{nome}.parquet" if nome == "ipca" else DESTINO / f"{nome}.parquet"
        )
        _escrever(con, nome, colunas, linhas, destino)
    (DESTINO / "manifesto.json").write_text(
        json.dumps({"tp_prestacao_contas": {"2022": "FINAL", "2026": "PARCIAL"}}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
