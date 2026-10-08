# Insumos manuais

## `mbl_2022.csv` (a ser fornecido pelo Felipe)
Lista dos candidatos do MBL nas eleições de 2022. Colunas mínimas (UTF-8, separador `,`):

| coluna | obrigatória | exemplo |
|---|---|---|
| `nome` | sim | nome de urna ou civil |
| `uf` | sim | `SP` |
| `cargo` | sim | `DEPUTADO FEDERAL` |
| `numero` | recomendada | `4444` (número na urna em 2022) |
| `sq_candidato` | opcional | se já conhecido |

**Não incluir CPF** — a ligação com 2026 é feita pelo ETL (ADR 0004).
O casamento com o cadastro oficial do TSE gera `mbl_2022_revisao.csv` com os casos ambíguos para
revisão humana (T-D06).
