# 0005 — Grupos de comparação configuráveis

- **Status:** aceito · 2026-10-07
- **Contexto:** hoje Missão 2026 × lista MBL 2022; amanhã outros partidos.
- **Decisão:** `config/grupos.yaml` define grupos por critério (`partido`, `lista`). Um resolvedor
  único transforma critério em filtro. Código não conhece "Missão" nem "MBL".
- **Consequências:** Open/Closed — novo partido é uma linha de configuração.
