# Handoff backend — T-B16 (comparativo por lado: validação)

Branch `fix/backend-comparativo-validacao` (sobre `origin/main` com a T-B15 #78). Commits: `test:` vermelho → `fix:`.

## O que mudou (`apps/api/src/api/servicos/comparativo.py`)
1. **sq fora do recorte** → 422 `sq_fora_do_recorte`, mensagem lista `ano/sq`. `pessoas` continua filtrando.
2. **Ordem**: `_por_lados` valida os grupos (`grupo_desconhecido`/`grupo_ano_errado`) antes de `_selecao` consultar o repositório.
3. **`mesmos_candidatos` em lado misto** (um lado grupo, outro candidatos): **decisão: rejeitar** com 422
   `mesmos_candidatos_lado_misto` (filtraria também o lado de grupo, descartando membros que o usuário não excluiu).
   Dois grupos: vale como antes. Dois lados de seleção: segue ignorado (a escolha já é do usuário). `description` do parâmetro atualizado.
4. **Critério do `n_para`**: `_n_aptas` → `n_em_disputa` (público, único lugar na API), documentado.
   Continua APTO + situação nula; diverge de `grupos.n_candidatos` (só APTO, spec §5.3) de propósito.
   **Pendência para a análise/orquestrador**: decidir se `packages/indicadores` passa a oferecer esse critério.
5. **Testes** `apps/api/tests/test_b16_validacao.py`. Fixtures não têm INDEFERIDO nem situação nula, então
   a contagem é testada em unidade (`n_em_disputa` com APTO + nula + INDEFERIDO + RENÚNCIA, sem I/O/mock de banco);
   sq de outro cargo/UF/ano (404 e 422) é integração real.

## Contrato
`docs/api/openapi.json` regenerado (só a descrição de `mesmos_candidatos`). Códigos novos de erro: `sq_fora_do_recorte`, `mesmos_candidatos_lado_misto` — avisar o frontend (o front que enviar `mesmos_candidatos=true` com lado misto passa a receber 422).

## Verificação
`make lint` e `pytest` Python verdes (660 passed, cobertura 95,8%). `make test` falha só no vitest do web
(`node_modules` ausente neste worktree; fora do meu território).
