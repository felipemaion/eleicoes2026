# Handoff — frontend T-W04 (telas completas)
Branch `feat/frontend-telas` (empilhada sobre `feat/frontend-graficos`, PR #31 — **integrar #31 primeiro**).

## O que foi feito
- **5 telas** com dados da API (`/api/*`): Visão geral, Mapa, Gastos, Evolução 2022×2026, Candidato — todas com estados carregando (`role=status`), erro (`role=alert` + "Tentar novamente") e vazio; `dispose` cancela resposta tardia e libera o WebGL.
- `src/dados/contrato.ts`: **único módulo** de tipos provisórios (endpoints de domínio da T-B02). `Meta` já vem do OpenAPI gerado.
- `pnpm gen:api` (openapi-typescript → `src/dados/gerado/api.d.ts`, commitado). Ao chegarem os endpoints no `openapi.json`: rodar `gen:api` e reexportar de `./gerado/api` em `contrato.ts`.
- `src/dados/cliente.ts`: um método por endpoint, guarda de forma mínima (falha alto com resposta inesperada).
- `src/dados/adaptadores.ts` (puro, 100% testado): filtros→query, KPIs §8.1 (KPI sem dado some, nunca vira 0), ranking/"só indicados", dispersão, avisos (contas parciais + mês-base do deflator por extenso), escala do mapa a partir de `escala_sugerida`, **mesmas quebras 2022/2026** (quantis de 2022∪2026), mapa de diferença divergente simétrico em 0.
- Candidato no estado/hash: `#/candidato?cand=2026:1` (validado por regex — vai para o caminho da API).
- **T-W03 (revisão do PR #31)** corrigida em commit próprio `5f81311` (itens 1–6 de `T-W03-revisao.md`).

## Decisões
- Coroplético só com taxas: `escalaDoMapa` passa por `validarCoropletico`; absolutos só como pontos (`/mapa/pontos` → `definirPontos`).
- Troca de indicador/candidato recolore via `feature-state` (geometria carrega 1×; ganchos `data-fontes`/`data-atualizacoes` mantidos para o e2e).
- Candidato: o seletor escreve no hash; `ligarStoreAoHash` redesenha (deep-link grátis).
- `Meta` real **não tem `fonte`** e `dt_geracao` não é nulo: cliente/rodapé ajustados (fonte é texto fixo).

## Pendências / limites conhecidos
- **Geometria**: só Sergipe (fixture) até os PMTiles (T-D04); telas avisam quando a UF ≠ SE. Níveis zona/H3 aparecem **desabilitados** ("em breve").
- Clique no mapa → painel não implementado (o componente não emite evento); usa-se o seletor "Resumo do município" (acessível). Candidato para T-W05.
- Tipos provisórios podem divergir do que o backend publicar (nomes de campos); ajuste fica restrito a `contrato.ts` + fixtures `tests/fixtures/api/`.
- Bundle > 500 kB (MapLibre): o import dinâmico já isola o mapa; code-splitting adicional fica para otimização.

## Como verificar
```bash
cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:e2e
```
Resultado local: 114 testes Vitest, 16 Playwright (fluxo por tela + erro/retry + 360 px), lint/tsc limpos.
**Lighthouse acessibilidade** (headless, API simulada com as fixtures): visão geral 100 · mapa 100 · gastos 100 · evolução 100 · candidato 100 (antes: gastos 91 por `aria-allowed-role`/`definition-list`, corrigidos).

## Proposta de diff para `.github/workflows/ci.yml` (do orquestrador)
No job `web`, após `pnpm build`:
```yaml
      - run: pnpm exec playwright install --with-deps chromium
      - run: pnpm test:e2e
```
(o `playwright.config.ts` já sobe `pnpm build && pnpm preview`; os testes usam fixtures via `page.route`, não precisam da API.)
