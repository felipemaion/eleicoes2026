# Handoff frontend — T-W17 (tooltip da dispersão)
Branch `fix/frontend-tooltip-foto` (a partir de `origin/main`).

**Causa da foto sumida:** o dado chegava certo (`foto_url` → `PontoCustoVoto.foto`). O `mousemove` recriava o conteúdo do balão a cada pixel, e a `<img loading="lazy">` era descartada antes de carregar; só aparecia quando já estava em cache (caso do Brasil). Agora: `mousemove` só reposiciona (`Flutuante.mover`) e a foto do tooltip é `eager`.

**Outras correções:** cabeçalho `.tooltip-cabeca` (foto + título) em vez de `float` (a lista de valores ocupa a largura toda, `nowrap` + `tabular-nums`); `<title>` nativo removido da dispersão (fica o `aria-label`).

**Verificar:** `pnpm vitest run` (307 ok), `pnpm exec playwright test tests/e2e/gastos-evolucao.spec.ts`.
**Atenção:** o Playwright usa `reuseExistingServer` na 4173; há um `vite preview` antigo (PID 16747) servindo build velho — rodei em outra porta. Mate-o ou rode com porta livre.
**Pendências:** nenhuma.
