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

Fonte: TSE, **divulgação oficial de resultados** (`resultados.tse.jus.br/oficial/ele2026/6258/dados/sp/sp66192-c0001-e006258-u.json`,
eleição 6258, município TSE 66192), gerada em 25/10/2026 21:11:33, **100% das seções apuradas** (974 de 974).
Conferência: válidos + brancos + nulos = comparecimento (261.933 + 3.488 + 8.515 = 273.936).
Ainda falta confirmar com os dados abertos (`votacao_candidato_munzona`, `nr_turno=2`) quando o TSE publicar.

| # | Candidato | Partido | Votos | % válidos |
|---:|---|---|---:|---:|
| 1 | Flávio Bolsonaro | PL | 161.594 | 61,69% |
| 2 | Lula | PT | 100.339 | 38,31% |
| | **Válidos** | | **261.933** | 100% |

| | Quantidade | % |
|---|---:|---:|
| Aptos | 337.853 | |
| Comparecimento | 273.936 | 81,08% dos aptos |
| Abstenção | 63.917 | 18,92% dos aptos |
| Brancos | 3.488 | 1,27% do comparecimento |
| Nulos | 8.515 | 3,11% do comparecimento |

### 1º × 2º turno

| | 1º turno | 2º turno | Diferença |
|---|---:|---:|---:|
| Flávio Bolsonaro | 145.880 | 161.594 | +15.714 |
| Lula | 76.564 | 100.339 | +23.775 |
| Demais candidatos (Cury, Renan, Caiado, Zema e outros) | 29.388 | — | −29.388 |
| Válidos | 251.832 | 261.933 | +10.101 |
| Brancos | 5.158 | 3.488 | −1.670 |
| Nulos | 9.341 | 8.515 | −826 |
| Comparecimento | 266.331 | 273.936 | +7.605 |
| Abstenção | 71.520 | 63.917 | −7.603 |
| Margem Flávio − Lula | 69.316 | 61.255 | −8.061 |

- Flávio venceu com folga em Jundiaí (61,69%); no país, com 99,98% das seções às 22:03, Lula tinha 51,78% contra
  48,22% — Jundiaí ficou **13,5 pontos mais à direita** que o resultado nacional.
- Dos 39.489 votos válidos que os dois finalistas ganharam do 1º para o 2º turno, **Lula ficou com 60%** (23.775) e
  Flávio com 40% (15.714): a margem caiu 8 mil votos. Entre só os dois, Lula passou de 34,42% (1º turno) para 38,31%.
- Esses votos vieram de três lugares: eleitores dos candidatos eliminados (29.388), 7.605 pessoas a mais votando e
  2.496 brancos e nulos a menos. **Não dá para dizer para onde foram os 9.927 eleitores do Renan**: o dado é por
  município, não por eleitor, e atribuir transferência a partir dele é falácia ecológica.

## Como refazer

Com os Parquet atualizados (`etl baixar` + `etl processar` dos dois datasets), em `.worktrees/dados`:

```python
import duckdb

D = "data/processed"
v = f"read_parquet('{D}/votacao_candidato_munzona/**/*.parquet', hive_partitioning=true, union_by_name=true)"
d = f"read_parquet('{D}/detalhe_votacao_munzona/**/*.parquet', hive_partitioning=true, union_by_name=true)"
f = "ano_eleicao=2026 and cd_mun_ibge=3525904 and ds_cargo ilike 'presidente' and nr_turno={t}"
for t in (1, 2):
    print(
        duckdb.sql(
            f"select nm_urna_candidato, sg_partido, sum(qt_votos_nominais_validos) v from {v} "
            f"where {f.format(t=t)} group by 1,2 order by v desc"
        ).fetchall()
    )
    print(
        duckdb.sql(
            f"select sum(qt_aptos), sum(qt_comparecimento), sum(qt_abstencoes), sum(qt_total_votos_validos), "
            f"sum(qt_votos_brancos), sum(qt_total_votos_nulos) from {d} where {f.format(t=t)}"
        ).fetchall()
    )
```
