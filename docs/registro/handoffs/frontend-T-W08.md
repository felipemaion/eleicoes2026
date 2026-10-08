# Handoff frontend — T-W08 (enquadramento do mapa e acabamento)

Branch `fix/frontend-enquadramento`.

## O que foi feito
1. **Enquadramento determinístico.** `src/dados/limites-uf.ts` (gerado por `scripts-dev/gerar-limites-uf.mjs` a partir de `ufs.geojsonl`, a mesma malha IBGE dos PMTiles) traz a caixa das 27 UFs. `limitesDosIds(ids)` une as caixas das UFs pelos 2 primeiros dígitos do id (município `3550308` ou zona `3550308-7`). `mapa.ts` chama `fitBounds` direto, sem esperar `idle` nem ler `querySourceFeatures` (removidos `agendarEnquadramento`/varredura de feições).
2. **"Sem dado" como token de tema.** `Tema.semDado` (`#c3c9d0` claro, `#4b535c` escuro) vira `--cor-sem-dado`. Mapa (pré-preenchimento e expressão `case`) e legenda usam o token; o mapa repinta ao trocar `prefers-color-scheme`. Teste de contraste em `paletas.test.ts` (≥1,5 do fundo, ≥1,2 da superfície, ≥1,3 da 1ª classe).
3. **Capturas** em `docs/registro/capturas/T-W08/` (tiles reais do ETL + API simulada com os ids reais): Brasil 360/1280; SP 360/485/768/1280; SE 485; AM 485 (3 UFs). Em todas a UF aparece inteira e centrada.

## Pendência — verificação em produção
O item 3 do brief (5 telas em produção com a API real) **não foi feito**: exige o deploy desta branch, que cabe ao orquestrador. Após o deploy, conferir `/#/mapa?uf=SP` em 485 px e as demais telas.

## Verificação
`cd apps/web && pnpm vitest run && npx tsc --noEmit && npx eslint . && pnpm exec playwright test` — 175 testes unitários verdes; 30 e2e passam (2 skipped, já existentes).
Para regenerar a tabela: `node scripts-dev/gerar-limites-uf.mjs <ufs.geojsonl>`.

## Decisões
- Tabela estática em vez de `/api/meta`: não exige endpoint novo e funciona antes de qualquer tile renderizar.
- Vizinhos da UF continuam cinza "sem dado" (a API só devolve a UF filtrada) — comportamento esperado, não bug.
