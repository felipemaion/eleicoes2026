# Handoff dados — T-D12 (receita × despesa)

## Resultado
**Não há falha de leitura no ETL.** Somas do CSV oficial = Parquet, em centavos (2026, ZIP de 07/10 e de 14/10):

| Candidato | Receita | Contratada | Paga | CSV = Parquet |
|---|---|---|---|---|
| Renan (…0694) | 269.013.031 → 281.547.753 | 128.682.837 → 128.862.519 | 128.682.837 → 128.862.519 | sim |
| Cury (…1547) | 355.635.086 → 385.638.370 | 54.549.091 → 140.703.076 | 52.749.091 → 130.703.076 | sim |
| Caiado (…1932) | 1.319.097.074 → 1.335.325.574 | 2.200.740.550 → 2.210.740.650 | 1.293.740.550 → 1.310.740.650 | sim |

(antes → depois do re-download de 14/10; receita em centavos.)

## Causa de cada divergência
- **Cury (15%)**: defasagem nossa (cache de 07/10; o TSE regera o ZIP todo dia) **+** estimáveis: receita estimável
  R$ 2,45 mi (partido) não tem despesa correspondente no arquivo. Hoje: 1,41/3,86 = 36% da total, **99,9% da financeira**.
- **Caiado (167%)**: declaração. Contratada R$ 22,1 mi > receita R$ 13,4 mi; **paga** = 100% da receita financeira.
  ~R$ 9 mi contratados e ainda não pagos. Sem duplicata (112 linhas/80 `SQ_DESPESA` = itens de nota).
- **Renan (48%)**: declaração parcial/saldo (contratada = paga = R$ 1,29 mi de R$ 2,82 mi). Não é leitura.
- Flávio/Zema ~97%: sem divergência a explicar.

## Respostas ao brief
2. Estimáveis: **arquivos de despesas não trazem despesa estimável**; ela só existe na receita (`ESTIMÁVEL` +
   `DS_NATUREZA_RECURSO_ESTIMAVEL`, categoria que o ETL hoje descarta). Provado com 2022 final.
3. Gasto do partido: há `prestacao_de_contas_eleitorais_orgaos_partidarios_{ano}.zip`, mas **sem vínculo ao candidato**;
   o benefício já está na conta dele (estimável/transferência). Somar = dupla contagem. Não ingerido.
4. Universo 2026 (14/10, N=16.900): fora de 70–110%: 10.154 abaixo / 759 acima (contratada ÷ receita total).
   Missão (N=490): mediana 83%; 202 abaixo / 14 acima. Detalhe em `docs/fontes-de-dados.md` (nova seção T-D12).

## Ações feitas
- Re-download + reprocesso local das contas 2026 (`etl baixar --fonte prestacao_contas`; `etl processar --dataset contas`):
  `data/processed` agora com `dt_geracao` 14/10. **Servidor ainda com 07/10**: precisa `make publicar-dados` + Deploy.
- Doc: seção nova em `docs/fontes-de-dados.md`. Sem código alterado, sem teste novo (não havia bug).

## Recomendações (fora do meu território)
- `analise`/`backend`: razão de gasto = **despesa ÷ receita financeira**; mostrar **paga** ao lado da contratada;
  avisar "contas parciais" (só 549 de 16.900 FINAL). Receita/voto pode seguir usando receita total.
- Opcional (T-D13?): guardar `DS_NATUREZA_RECURSO_ESTIMAVEL` no Parquet de receitas para abrir a estimável por categoria.

## Como verificar
`uv run etl baixar --ano 2026 --fonte prestacao_contas` e comparar a soma de `VR_*` de `*_BR.csv` com o Parquet.
Scripts de conferência ficaram no scratchpad (não versionados).
