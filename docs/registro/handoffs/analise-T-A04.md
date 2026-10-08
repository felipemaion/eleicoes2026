# Handoff — analise · T-A04 (conferência contra o TSE)

**Branch:** `docs/analise-conferencia` (rebaseada em `origin/main` em 2026-10-08). Commits:
`test(indicadores): …` (vermelho) → `feat(indicadores): conferência … (T-A04)` → este handoff.

## O que foi feito
- `packages/indicadores/src/indicadores/conferencia.py` — funções puras: leitura do JSON de
  divulgação do TSE (`divulgacao_totais/candidatos/partidos`), `classificar_votavel` (seção:
  nominal/legenda/branco/nulo) e `comparar` (nosso × fonte, longo, situação
  confere/diverge/so_nosso/so_fonte). 13 testes, cobertura 100%.
- `packages/indicadores/scripts/conferir.py` — script reproduzível (rede só nele, cache em
  `~/.cache/eleicoes2026/conferencia`, lê os zips do TSE em fluxo, sem descompactar).
- `docs/metodologia/conferencia.md` — relatório: fonte × nosso × diferença, explicações.
- `docs/metodologia/cuidados.md` — itens 9–12 (inapto → nulo, legenda total, `BR.parquet`,
  custo por voto sem repasses).

## Resultado
**Nenhuma divergência real.** 2026: 40.553 comparações contra o JSON de divulgação (27 UFs +
presidente BR; todo o Missão), diferença 0. 2022: o JSON saiu do ar → `votacao_secao` +
`detalhe_votacao_secao` agregados do zero; 9.617 comparações, diferença 0 após reconciliar a
única regra (voto em candidato INAPTO / legenda sem registro → nulo; 235 candidatos omitidos
pelo TSE do munzona, todos INAPTO, ex. Daniel Silveira RJ 1.566.352). MBL 2022: 16/18 conferidos
(Helio Secco vice sem voto; Luziane inapta). Custo por voto de Kim, Guto e Renato conferido à
mão no DivulgaCandContas: despesas, pagas e receitas iguais ao centavo.

## Decisões
- Fonte de 2022 = arquivos por seção (independentes do `*_munzona`), já que
  `resultados.tse.jus.br/oficial/ele2022/...` retorna 404.
- Total de 2022 compara "nominais + legenda" juntos: o `detalhe_votacao_munzona` de SP embute os
  convertidos em `qt_votos_leg_validos` (587 / 6.990). Legenda por partido é conferida à parte.

## Pendências / avisos para outros papéis
- **backend/frontend:** presidente está só em `BR.parquet` (somar UFs zera o cargo 1); legenda
  total = `leg_validos + nom_convr_leg_validos` (nunca `qt_votos_leg_validos` sozinho em 2022);
  tooltip do custo por voto deve dizer que exclui repasses (Kim: TSE 470.347,01 × nosso 405.448,51).
- **dados (pré-existente, não é desta tarefa):** `packages/etl/tests/test_processar.py::
  test_cpf_nunca_toca_processed` falha na suíte completa em `origin/main` (FileNotFoundError em
  `…/etl-*/municipio_tse_ibge.utf8.csv`, temp dir); passa isolado → provável dependência de
  ordem/tmp compartilhado. Sem diff meu em `packages/etl`.
- `make lint` do web falha neste worktree só por falta de `node_modules` (ambiente).
- Rerodar `conferir.py` quando: sair o 2º turno de 2026 (acrescentar turno 2), o TSE reprocessar
  sub judice, ou o ETL mudar. Contas de 2026 são parciais.

## Como verificar
```bash
uv run pytest packages/indicadores -q
uv run python packages/indicadores/scripts/conferir.py \
    --processed /Users/maion/Projects/Eleicoes2026/.worktrees/dados/data/processed \
    --saida /tmp/conferencia   # exit 0; resumo em /tmp/conferencia/resumo.md
```
Cache já baixado (~2,2 GB) em `~/.cache/eleicoes2026/conferencia` (pode apagar; rebaixa sozinho).
Disco da máquina estava com ~8 GB livres.
