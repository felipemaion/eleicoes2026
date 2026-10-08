"""Gera as fixtures Parquet de teste (contrato provisório até T-D02).

Os nomes de colunas seguem a seção "Colunas × fontes" de docs/metodologia/indicadores.md, já
em minúsculas (tradução TSE→domínio é do ETL). Mundo pequeno, conferível à mão:

* 2026 Dep. Federal SP — Missão (14): sq 3 (1000 votos, receitas/despesas do vetor da spec),
  sq 5 (180 votos); sq 7 (PP, entra em mbl_2026 pela lista) e sq 6 (outro partido).
* 2022 Dep. Federal SP — MBL 2022: sq 1 (=pessoa A, sq 3 em 2026), sq 8, sq 9 (=pessoa D, sq 7 em 2026).
* Dep. Estadual RJ: sq 2 (2022) e sq 4 (2026), mesma pessoa C.

Uso: uv run python apps/api/scripts/gerar_fixture.py
"""

import json
from pathlib import Path

import duckdb

DESTINO = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
DF, DE = "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"
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
            (2026, 3, "pA", "A", "SP", DF, 14, "MISSÃO", "APTO", "SUPLENTE"),
            (2026, 4, "pC", "C", "RJ", DE, 14, "MISSÃO", "APTO", "NÃO ELEITO"),
            (2026, 5, "pB", "B", "SP", DF, 14, "MISSÃO", "APTO", "NÃO ELEITO"),
            (2026, 6, "pF", "F", "SP", DF, 15, "MDB", "APTO", "ELEITO POR MÉDIA"),
            (2026, 7, "pD", "D", "SP", DF, 11, "PP", "APTO", "ELEITO POR QP"),
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
            (2026, 4, RIO, 1, 400),
            (2022, 1, SP, 1, 500),
            (2022, 1, SP, 2, 200),
            (2022, 1, CAMP, 1, 100),
            (2022, 8, SP, 1, 300),
            (2022, 9, CAMP, 1, 60),
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
            (2026, 7, SP, 1, 1001, 300),
            (2026, 7, SP, 1, 1002, 200),
            (2026, 7, CAMP, 1, 3001, 200),
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
            (2026, 3, "OUTROS RECURSOS", "Recursos de Financiamento Coletivo", "FINANCEIRO", 8000.0),
            (2026, 3, "OUTROS RECURSOS", "Recursos de pessoas físicas", "ESTIMADO", 2000.0),
            (2026, 3, "OUTROS RECURSOS", "Recursos de outros candidatos", "FINANCEIRO", 7000.0),
            (2026, 3, "OUTROS RECURSOS", "Rendimentos de aplicações financeiras", "FINANCEIRO", 3000.0),
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


def main() -> None:
    """Escreve todos os Parquet e o manifesto em tests/fixtures."""
    DESTINO.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for nome, (colunas, linhas) in TABELAS.items():
        con.execute(f"CREATE TABLE {nome}({_ddl(colunas, linhas[0])})")  # noqa: S608
        marcas = ", ".join("?" * len(linhas[0]))
        con.executemany(f"INSERT INTO {nome} VALUES ({marcas})", linhas)  # noqa: S608
        con.execute(f"COPY {nome} TO ? (FORMAT PARQUET)", [str(DESTINO / f"{nome}.parquet")])
    con.execute("CREATE TABLE ipca(mes VARCHAR, variacao DOUBLE)")
    con.executemany("INSERT INTO ipca VALUES (?, ?)", IPCA)
    con.execute("COPY ipca TO ? (FORMAT PARQUET)", [str(DESTINO / "ipca.parquet")])
    (DESTINO / "manifesto.json").write_text(
        json.dumps(
            {
                "dt_geracao": "2026-10-06T12:00:00",
                "tp_prestacao_contas": {"2022": "FINAL", "2026": "PARCIAL"},
            },
            indent=2,
        )
        + "\n"
    )


def _ddl(colunas: str, amostra: tuple[object, ...]) -> str:
    tipos = {int: "BIGINT", float: "DOUBLE", str: "VARCHAR"}
    nomes = [c.strip() for c in colunas.split(",")]
    return ", ".join(f"{n} {tipos[type(v)]}" for n, v in zip(nomes, amostra, strict=True))


if __name__ == "__main__":
    main()
