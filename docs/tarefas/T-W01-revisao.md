# T-W01 — correções da revisão (PR #25)
Corrigir no branch `feat/frontend-scaffold` (TDD), commitar, e depois rebasear seu branch da T-W02 sobre ele:
1. [BLOQUEANTE] `index.html:10` skip link `href="#principal"` dispara `hashchange` → `lerHash` reseta
   tela e filtros. `lerHash` deve ignorar hashes que não começam com `#/` (sem reescrever estado) e/ou
   o clique faz `preventDefault()` + `principal.focus()`. Teste unitário + e2e.
2. [ALTA] `telas/tipos.ts`: `Tela.render` sem desmontagem; `main.ts` re-renderiza a cada mudança →
   MapLibre/D3 vão vazar WebGL/listeners. `render` devolve `() => void` (dispose) e `main.ts` chama
   antes do próximo render/troca de tela. Teste que o dispose é chamado.
3. [ALTA] `dados/cliente.ts:21` cast `as Meta` sem validação: guard de runtime mínimo (ou `unknown`
   até o contrato gerado existir).
4. [ALTA] `paletas.test.ts:11-13` teste "divergente simétrica com neutro claro" só checa `/^#/`:
   afirmar luminância/contraste do neutro e simetria dos extremos — ou remover.
5. Curtas: `filtros.ts:32` tipagem da chave computada; `assinar` devolver unsubscribe;
   filtros com `history.replaceState` em vez de empilhar histórico.
