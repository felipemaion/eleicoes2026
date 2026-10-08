# Handoff — analise · T-A02 (biblioteca `indicadores`)

- **Branch:** `feat/analise-indicadores`, criada sobre `docs/analise-spec-indicadores` (T-A01,
  PR #27 ainda fora da main) · 2026-10-07. Integrar **depois** do PR #27 (ou rebase sobre ele).
- Commits: `test:` (vermelho: ImportError dos módulos) → `feat:` → `docs:` (spec + handoff).

## O que foi feito
Funções puras polars→polars em `packages/indicadores/src/indicadores/` (sem I/O, sem estado,
docstring com fórmula e referência):
- `desempenho.py` — `votos_nominais` (zona→município, destinações separadas),
  `montar_tabela` (entidade × unidade com zeros explícitos), `pct_validos`, `penetracao`,
  `indicadores_municipais` (tudo de uma vez: %válidos, ‰, LQ, n baixo), `totais_uf`,
  `quociente_eleitoral` (CE art. 106, aritmética inteira), `votacao_partido` (legenda total,
  QE, votação em QE, QP), `votos_km2`.
- `espacial.py` — `n_baixo`, `lq`, `concentracao` (HHI, N efetivo, D de Ames, G),
  `tipologia_ames`, `suavizacao_eb` (Marshall 1991), `moran_lisa` (+ pseudo-p por permutação,
  semente 20261004), `agregar_h3`, `cobertura_h3`.
- `financeiro.py` — `classificar_receitas` (tabela fechada; rótulo novo falha), `resumo_receitas`,
  `despesa_campanha` (sem repasses), `custo_por_voto`, `custo_por_voto_agregado` (Σ/Σ + mediana),
  `serie_ipca`, `fator_ipca`, `resolver_mes_base` (emenda ADR 0007), `corrigir_ipca`.
- `evolucao.py` — `agregar_amc`, `evolucao` (Δpen, swing, retenção, ganho), `spearman`,
  `sobreposicao_redutos`, `por_candidato`, `mesmos_candidatos`.
- `grupos.py` — `agregar_grupo` (candidato coletivo; recusa cargos/turnos misturados),
  `n_candidatos` (aptas), `receitas_grupo` (sem transferência interna).
- `entidade="grupo"` faz qualquer indicador de candidato valer para grupo (sem código novo).

## Critérios de aceite
1. **Todos os 31 casos dos 18 vetores passam** (`tests/test_vetores_impl.py`, um adaptador por
   vetor, tolerância do próprio vetor; casos `erro` exigem `ValueError` com a mensagem).
   Cobertura de `indicadores`: **99 %** (390 stmts, 3 linhas de guarda não exercitadas).
2. `ruff check`, `ruff format --check` e `mypy --strict` limpos.
3. `tests/test_desempenho_lento.py` (`@pytest.mark.lento`, marcador registrado no `conftest.py`
   do pacote): SP sintético, 645 municípios × 1.500 candidaturas → tabela municipal + concentração
   + totais UF em **≈ 0,22 s** (limite 2 s).

## Decisões (detalhe em `docs/metodologia/indicadores.md` §8-A, nova)
- Tabela completa entidade × unidade; falha alto em duplicata, voto sem eleitorado, votos > válidos.
- Taxa de referência do n baixo = penetração da entidade na UF; esperado nulo = n baixo.
- LISA: zero conta como "baixo"; ilha falha (k = 1 é responsabilidade de quem monta W).
- Spearman usa todas as AMCs com LQ definido; `n_baixo` só filtra redutos.
- Rótulos TSE comparados normalizados (caixa/acento).
- Spec §1.6 atualizada com a emenda do ADR 0007 (base = último mês disponível).

## Divergências / pendências
- **`packages/contratos` está vazio na main** (T-D02 em andamento): nomes de coluna vêm da spec
  §7 (domínio, minúsculas). Quando T-D02 entrar, trocar literais por constantes do contrato
  (só nomes; nenhuma regra muda) — tarefa curta minha.
- **dados:** a classificação financeira e `NM_TIPO_DESTINACAO_VOTOS` estão fechadas com os
  rótulos conhecidos; rótulo novo **falha** de propósito. Preciso dos valores distintos de 2022 e
  2026 (`DS_FONTE_RECEITA`, `DS_ORIGEM_RECEITA`, `DS_NATUREZA_RECEITA`, `DS_ORIGEM_DESPESA`,
  `NM_TIPO_DESTINACAO_VOTOS`). Em especial: repasse excluído da despesa hoje é só "Doações
  financeiras a outros candidatos/partidos".
- **backend:** a API resolve `config/grupos.yaml` → lista de `sq_candidato` e chama
  `grupos.agregar_grupo`, depois os indicadores com `entidade="grupo"`. Moran/LISA recebe
  `vizinhanca` (arestas rainha + k=1 para ilhas) já montada — geometria fica fora da lib.
- `make test` falha só na parte web neste worktree (`vitest: command not found`, sem
  `node_modules`) — ambiente, fora do meu território; Python: 177 passed, 97 % cobertura.

## Como verificar
```bash
uv run pytest packages/indicadores -q --cov=packages/indicadores/src --cov-report=term-missing
uv run pytest packages/indicadores -m lento --durations=1
uv run ruff check packages/indicadores && uv run ruff format --check packages/indicadores
uv run mypy packages/indicadores/src
```
