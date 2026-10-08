# Handoff frontend — T-W06 (pronto para produção)
Branch `feat/frontend-producao` (sobre `feat/frontend-integracao`). Sem push.

## O que foi feito
1. **Same-origin**: nenhuma URL absoluta de dev no bundle (`/api/*`, `/tiles/manifesto.json`, `/tiles/<arquivo>`); `base: "/"` explícito no Vite. Adicionado `apps/web/Caddyfile` (`/api`→:8000, `/tiles/*` com Range via `file_server`, `/assets/*` imutável, SPA fallback). **Não testado**: `caddy` não está instalado aqui; serve de referência ao agente Oracle.
2. **Hachura de n baixo** (`src/dados/n-baixo.ts`, `componentes/mapa/mapa.ts`): camada `fill-pattern` com `fill-opacity` por `feature-state` (fill-pattern não aceita feature-state). Legenda com chave da hachura, linha "Estimativa" no tooltip e coluna "Estimativa" na tabela alternativa; aviso público `n_baixo` reativado na tela Mapa. Conferido em captura de tela com município forçado.
3. **Lighthouse (desktop, v12, headless) + axe**: ver tabela. axe (WCAG 2.2 AA) em `tests/e2e/a11y.spec.ts`, 0 violações nas 6 telas.
4. **Bundle**: JS inicial **45,2 kB gzip** (meta < 200). MapLibre/PMTiles já eram `import()` dinâmico (chunk `mapa-*.js`, 292 kB gzip, só na tela com mapa). Split por tela **não feito**: seria render assíncrono em todas as telas sem ganho de meta; fica como opção.
5. **`<head>`**: description, OG, Twitter card, `og.png` 1200×630 (gerado uma vez por `scripts-dev/gerar-og.mjs`, versionado em `public/`), favicon SVG, `theme-color`, `lang="pt-BR"`, `noscript`, `robots.txt`. **404 de rota de hash** (`rotaExiste`).
6. **Rodapé**: fontes, `dt_geracao`, links Metodologia (`#/como-ler`) e GitHub.
7. **CLS**: `main` com `min-height:100vh` e `.mapa-area` com altura mínima (CLS 0,64→0). Legenda: "sem dado" não é mais cortado.

## Lighthouse / axe (servidor local com fixtures do contrato; tiles 404 → mapa usa GeoJSON de demonstração)
| Tela | Perf | A11y | Boas práticas | SEO | LCP ms | TBT ms | CLS |
|---|---|---|---|---|---|---|---|
| visão geral | 100 | 100 | 100 | 100 | 364 | 0 | 0 |
| mapa (SE) | 100 | 100 | 96* | 100 | 368 | 0 | 0,03 |
| gastos | 100 | 100 | 100 | 100 | 365 | 0 | 0 |
| evolução | 100 | 100 | 96* | 100 | 688 | 0 | 0 |
| candidato | 100 | 100 | 100 | 100 | 364 | 0 | 0 |
| como ler | 100 | 100 | 100 | 100 | 364 | 0 | 0 |
\* console 404 do `/tiles/manifesto.json` no mock (esperado até publicar os tiles).
Antes das correções de CLS: gastos 77, mapa 84 (TBT 302 antes de reservar espaço), evolução 94. Medido sem rede real nem API real: **repetir contra produção** após deploy.

## Decisões / pendências
- **`n_baixo` é derivado no cliente** porque `/mapa` não o expõe: `E = aptos × (Σvotos/Σaptos da UF, UF = 2 primeiros dígitos do IBGE) < 20`. Com filtro de UF a referência é só o que a resposta traz (municípios sem voto entram com votos 0), e com `pct_validos` o `E` continua usando aptos (spec §1.4). **Pedido ao backend (via orquestrador)**: expor `n_baixo` em `Detalhe` para o front trocar a derivação pela marca oficial.
- Território sem dado (denominador 0, cinza) não recebe hachura: já é "sem dado".
- Nenhuma imagem OG por rota: é uma só, estática.

## Verificar
```
cd apps/web && pnpm lint && pnpm typecheck && pnpm vitest run && pnpm test:e2e   # 169 unit, 29 e2e (2 pulados: API real)
pnpm build   # index-*.js ≈ 45 kB gzip
```
