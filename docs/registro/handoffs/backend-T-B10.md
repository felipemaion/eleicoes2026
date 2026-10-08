# Handoff backend T-B10 (branch `feat/backend-pedidos-w12`)

**Feito**
- `/api/gastos` → `por_candidato[]` ganha `partido {numero,sigla}`, `resultado` (`ds_sit_tot_turno`),
  `pct_publico`, `pct_autofinanciamento` (por candidato, via `financeiro.resumo_receitas`; null sem receita).
- `/api/evolucao/pessoas?pessoas=<id>&pessoas=<id>`: as escolhidas entram sempre, além da página do
  recorte (`limite`), sem duplicar; ids desconhecidos são ignorados; formato inválido = 422. Total continua sendo o do recorte.
  `Repositorio.pares_de_pessoas` ganhou `publicos=` (DuckDB e memória).
- `varredura.py` cobre `/api/candidatos/ufs` (por ano, ano×cargo, grupo, grupo×cargo).
- OpenAPI regenerado (`docs/api/openapi.json`). Mudança só aditiva.

**Verificar:** `uv run pytest apps/api -q` · `make lint` · `apps/api/tests/test_b10_pedidos_w12.py`.
**Pendências:** nenhuma.
