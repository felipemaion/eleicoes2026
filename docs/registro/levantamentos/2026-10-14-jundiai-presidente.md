# Levantamento — Presidente em Jundiaí-SP (IBGE 3525904), 2026

Pedido do Felipe (14/10): votos para presidente em Jundiaí por candidato, brancos e nulos; **refazer após o
2º turno** (25/10/2026) — acrescentar a seção do 2º turno abaixo quando o TSE publicar.

Fonte: TSE, `votacao_candidato_munzona` e `detalhe_votacao_munzona` 2026 (`dt_geracao` 2026-10-07), somando as
zonas do município. Conferência: válidos + brancos + nulos = comparecimento (251.832 + 5.158 + 9.341 = 266.331).

## 1º turno (04/10/2026)

| # | Candidato | Partido | Votos | % válidos |
|---:|---|---|---:|---:|
| 1 | Flávio Bolsonaro | PL | 145.880 | 57,93% |
| 2 | Lula | PT | 76.564 | 30,40% |
| 3 | Augusto Cury | Avante | 10.851 | 4,31% |
| 4 | **Renan Santos** | **Missão** | **9.927** | **3,94%** |
| 5 | Ronaldo Caiado | PSD | 6.191 | 2,46% |
| 6 | Romeu Zema | Novo | 1.484 | 0,59% |
| 7 | Samara | UP | 491 | 0,19% |
| 8 | Hertz Dias | PSTU | 161 | 0,06% |
| 9 | Clariana Barão | DC | 116 | 0,05% |
| 10 | Edmilson Costa | PCB | 63 | 0,03% |
| 11 | Rui Costa Pimenta | PCO | 56 | 0,02% |
| 12 | Veterinário Wilson Grassi | Democrata | 48 | 0,02% |
| | **Válidos** | | **251.832** | 100% |

| | Quantidade | % |
|---|---:|---:|
| Aptos | 337.851 | |
| Comparecimento | 266.331 | 78,83% dos aptos |
| Abstenção | 71.520 | 21,17% dos aptos |
| Brancos | 5.158 | 1,94% do comparecimento |
| Nulos (9.329 + 12 técnicos) | 9.341 | 3,51% do comparecimento |

Renan Santos: 3,94% dos válidos em Jundiaí contra 2,24% no país.

## 2º turno (25/10/2026)

_Pendente — refazer quando o TSE publicar o resultado do 2º turno._

## Como refazer

Com os Parquet atualizados (`etl baixar` + `etl processar` dos dois datasets), em `.worktrees/dados`:

```python
import duckdb
D = "data/processed"
v = f"read_parquet('{D}/votacao_candidato_munzona/**/*.parquet', hive_partitioning=true, union_by_name=true)"
d = f"read_parquet('{D}/detalhe_votacao_munzona/**/*.parquet', hive_partitioning=true, union_by_name=true)"
f = "ano_eleicao=2026 and cd_mun_ibge=3525904 and ds_cargo ilike 'presidente' and nr_turno={t}"
for t in (1, 2):
    print(duckdb.sql(f"select nm_urna_candidato, sg_partido, sum(qt_votos_nominais_validos) v from {v} "
                     f"where {f.format(t=t)} group by 1,2 order by v desc").fetchall())
    print(duckdb.sql(f"select sum(qt_aptos), sum(qt_comparecimento), sum(qt_abstencoes), sum(qt_total_votos_validos), "
                     f"sum(qt_votos_brancos), sum(qt_total_votos_nulos) from {d} where {f.format(t=t)}").fetchall())
```
