# Handoff frontend — T-W07 (mapa vazio em produção)

Branch: `fix/frontend-mapa-producao`.

## Causa raiz
Os PMTiles foram gerados com `zoom_min=3` (`packages/etl/src/etl/geo.py`). Em tela estreita o MapLibre enquadrou o Brasil em zoom ≈ 2,4, onde o arquivo não tem nenhuma feição: `queryRenderedFeatures()=0`, sem erro algum. Reproduzido contra a produção (430 px, tema escuro). O `feature-state` e a fonte estavam corretos.
Em desktop o mapa aparecia, mas com o Brasil inteiro cinza, porque só SP tem valor e o mapa não enquadrava a UF.

## O que mudou (apps/web)
- `componentes/mapa/mapa.ts`: `minZoom: 3` quando há fonte PMTiles. Enquadra as áreas com valor (a UF filtrada), usando as feições carregadas e tentando de novo até 3× no `idle`.
- `telas/mapa.ts`: densidade **desligada por padrão**. Falha em `/mapa/pontos` não derruba o coroplético: aviso discreto (`.aviso-pontos`), checkbox desabilitado, detalhe no console.
- `telas/estados.ts`: `mostrarErro` mostra mensagem amigável (sem URL/status); detalhe em `console.error`. CSS `overflow-wrap:anywhere` em `.estado`.
- `telas/evolucao.ts`: **bug extra achado no item 4**. `/api/comparativo` exige `comparacao` e a 1ª chamada ia sem ela (422, tela de erro). Agora busca `grupos` antes e usa a primeira comparação.
- Testes: e2e "pontos 503 → coroplético renderiza", "erro sem URL crua / sem estouro de largura", "evolução envia comparacao"; unit e e2e antigos ajustados à densidade desligada e à mensagem amigável.

## Verificação
`cd apps/web && pnpm exec tsc --noEmit && pnpm exec eslint src tests && pnpm exec vitest run && pnpm exec playwright test` → verde (169 unit, 32 e2e, 2 skipped).
Visual contra os tiles reais de produção (app local com `/api` e `/tiles` roteados à produção): SP enquadrada e colorida em 430 px escuro e em 1280 px.

## As 5 telas na produção (antes do fix) — capturas em `docs/registro/capturas-T-W07/`
- visão geral, gastos, candidato, como ler: sem erros, sem rolagem horizontal.
- mapa: 503 em `/api/mapa/pontos` (esperado até T-D05) + o mapa vazio. Corrigidos.
- evolução: 422 em `/api/comparativo`. Corrigido (acima).

## Pendências
- `/api/mapa/pontos` segue 503 até T-D05 subir; a densidade fica desabilitada com aviso.
- Cor "sem dado" fixa `#d9d9d9` no tema escuro: legível, mas clara; avaliar token de tema.
- Se o ETL baixar `zoom_min`, ajustar `ZOOM_MIN_PMTILES` (ou ler do manifesto).
