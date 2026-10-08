# Insumos manuais

## `mbl_2022.csv` — grupo MBL 2022 (18 candidaturas)

Gerada em 2026-10-07 a partir do cadastro oficial do TSE (`consulta_cand_2022` e
`consulta_cand_2026`, arquivos `_BRASIL`, 1º turno). Critério definido pelo Felipe:

1. **Indicados** (`origem = indicado`): Kim Kataguiri, Guto Zacarias, Renato Battista e Cristiano
   Beraldo (este concorreu em 2026 pelo PP e deve ser incluído).
2. **Candidatos do Missão em 2026 que também disputaram 2022** (`origem = missao_2026_disputou_2022`),
   por qualquer partido — ligados pelo CPF **apenas em memória**; o CPF não é gravado.

Quando a pessoa teve mais de um registro em 2022, ficou o registro `APTO`.

| coluna | conteúdo |
|---|---|
| `nome`, `nome_civil` | nome de urna e nome civil em 2022 |
| `uf`, `cargo`, `numero`, `sq_candidato` | candidatura de 2022 (UF de 2022) |
| `partido_2022`, `situacao_2022`, `resultado_2022` | partido, aptidão e resultado em 2022 |
| `cargo_2026`, `partido_2026`, `numero_2026`, `sq_candidato_2026`, `resultado_2026` | candidatura de 2026 |
| `origem` | `indicado` ou `missao_2026_disputou_2022` (permite filtrar o recorte) |
| `observacao` | ressalvas que afetam a soma de votos (ver abaixo) |

### Ressalvas que afetam a comparação
- **Luziane Escritora (BA)**: inapta em 2022 → votos anulados (não somam).
- **Helio Secco (RJ)**: vice-governador em 2022 → sem voto nominal próprio.
- **Moisés Queiroz (RJ)**: 1º suplente de senador em 2026 → sem voto nominal em 2026.
- **Sargento Sousa**: 2022 pelo MA, 2026 por SP.
- **Cristiano Beraldo**: também teve registro de dep. estadual (44555, situação `#NULO`) em 2022.
- Vários nomes do recorte `missao_2026_disputou_2022` não eram do MBL em 2022; o filtro por
  `origem` permite comparar só os indicados.

A reprodução automatizada desta lista no ETL (com `pessoa_id`, ADR 0004) é a tarefa T-D06.
**Nunca incluir CPF neste arquivo.**
