# Handoff frontend — T-W15 (hover com foto; clique abre o TSE)

**Feito**
- Tipos regenerados (`pnpm gen:api`) com `foto_url` e `link_tse_candidato`; fixtures do contrato atualizadas (sq 3 sem foto) e `tipado.ts` estreita o `tipo` do link (`gastosTipados` novo).
- `componentes/ui/foto-candidato.ts`: `figuraCandidato` (img 80×100 `loading=lazy`, `alt="Foto de <nome>"`; `null` → iniciais), `avisoLinkTse`, `abrirNoTse` (`window.open(url,"_blank","noopener,noreferrer")`, só https).
- `corpoRico` aceita `foto` e `rodape`; dispersão de Gastos mostra foto + "Clique para abrir no TSE (nova aba)." e, se `verificado=false`, a nota. Clique e Enter no círculo abrem o link (`role=link`).
- Busca: miniatura 32×40 em cada sugestão (consistência). Ranking não mostra candidatos individuais → não alterado.

**Decisões**: só `https://` abre; sem link no ponto, o círculo não vira link.

**Verificar**: `cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm exec playwright test` (e2e novo em `gastos-evolucao.spec.ts`; `window.open` é espiado). Atenção: `playwright` reaproveita o preview da :4173 — rode `pnpm build` antes.

**Pendências**: foto real só aparece em produção quando `public/fotos` estiver publicado (T-D07/deploy).
