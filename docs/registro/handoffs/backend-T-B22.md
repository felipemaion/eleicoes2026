# Handoff backend — T-B22 (/municipios 422 pelo grupo de ranking)

**Branch:** `fix/backend-municipio-grupo-ranking` (a partir de `origin/main` 842b35e; a branch antiga da T-B21 já estava integrada via #104).

## O que fez
- `Catalogo.grupos_por_lista()` (`servicos/grupos.py`): único ponto que exclui grupos `ranking`.
- Usado nos três laços sobre todos os grupos: `servicos/municipio.py` (causa do 422), `aquecimento.py` (`_plano`) e `listar_grupos`.
- `tests/test_b22_grupo_ranking.py`: catálogo **real** `config/grupos.yaml` + mundo de referências; cobre `/municipios`, aquecimento, `/grupos` e `/candidatos` por grupo (ranking segue 422 `grupo_por_ranking`, os demais 200).

## Decisões
- Sem mudança de contrato/OpenAPI (resposta de `/municipios` só deixa de falhar).
- Os testes do aquecimento com catálogo real não exigem `erros == 0`: o MBL real não existe nas fixtures e os comparativos recusam (`sem_par_comparavel`); o que se garante é que o plano segue e não inclui o ranking.

## Pendências
- Opcional não feito: `comparativo.py:239` e `escopo.py:32` (`sq` explícito fora da urna entra em contagens) — não era pequeno o suficiente sem brief próprio.
- Deploy: após o merge, o workflow Deploy publica a correção.

## Como verificar
`uv run pytest apps/api -q` (verde); `ruff` e `mypy --strict` limpos.
Produção: `GET /api/municipios/3550308` deve dar 200 sem `top5_eleitos_outros_2026`.
