# Handoff — analise · T-A05 (textos públicos de metodologia e glossário)

Branch `docs/analise-textos-publicos` (a partir de `origin/main`). Commits: `test:` (vermelho) → `docs:`.

## O que foi feito
- `docs/metodologia/publico/textos.json` (versão 1), consumido pelo frontend:
  - `indicadores` — **24 chaves**: as 18 da spec (nome do vetor = chave, igual a
    `docs/metodologia/vetores/*.json`) + 6 sub-indicadores exibidos isoladamente em KPIs/tabelas
    (`votacao_em_qe`, `indice_g`, `dominancia`, `pct_publico`, `pct_autofinanciamento`, `divida`).
    Campos: `titulo, resumo (≤160), como_ler (≤400), unidade, denominador, cuidado (≤300), fonte`
    + `vetor` (arquivo do vetor) e `spec` (âncora em `indicadores.md`) para o frontend linkar.
  - `telas` — `visao_geral, mapa, gastos, evolucao, candidato`: `titulo, subtitulo, nota_rodape`
    + listas `indicadores` e `avisos` que a tela exibe.
  - `avisos` — os 5 pedidos (`contas_parciais`, `legenda_nao_atribuida`, `rezoneamento`,
    `grupo_mbl_2022`, `numero_14_em_2022`) + `resultado_sub_judice`, `n_baixo`, `ipca`,
    `senado_fora_evolucao`; cada um com `titulo, texto, nivel (info|atencao)`.
  - `glossario` — 24 termos (`termo`, `definicao ≤300`).
  - `limites` (os limites de tamanho, fonte única para teste e frontend) e `placeholders`.
- `docs/metodologia/publico/README.md` — página "Como ler este painel".
- `packages/indicadores/tests/test_textos_publicos.py` — 10 testes: toda chave de vetor da spec
  tem texto; campos e limites; `vetor`/`spec` existem; telas completas; avisos obrigatórios;
  todo aviso é usado por alguma tela; glossário; placeholders declarados; espaços; README cobre
  os temas-chave.

## Decisões
- **Placeholders** `{dt_geracao}` e `{mes_base_ipca}`: o frontend substitui (DT_GERACAO do
  manifesto e mês-base do IPCA devolvido pela API). Isso já segue a emenda IPCA da T-A02 (ADR
  0007: base = último mês disponível até sair set/2026), que ainda não está na `main`.
- Grupo MBL 2022: números (18 = 4 indicados + 14) conferidos em `data/reference/mbl_2022.csv`.
  Um dos 18 era do próprio PTB em 2022 — reforça o aviso do número 14.
- Texto público sem fórmulas; fórmulas ficam em `indicadores.md` (link por `spec`).

## Pendências
- Se a spec ganhar indicador novo (vetor novo), o teste falha até haver texto — intencional.
- Frontend: renderizar `textos.json` (tooltips "?", rodapés, banners de aviso) e publicar o
  README como página — tarefa do `frontend`.
- `make lint` falha no worktree só por `eslint` ausente (web sem `node_modules`); ruff, format e
  mypy verdes.

## Como verificar
```bash
uv run pytest -q packages/indicadores/tests/test_textos_publicos.py
uv run ruff check . && uv run mypy --strict packages/indicadores
```
