# T-W02 — correções da revisão (PR #26) — branch `feat/frontend-mapa`
1. `escalas.ts:71-72` quantil com muitos zeros: classe 0 vazia rotulada "< 0", zeros na 2ª cor, topo da
   paleta nunca usado. Descartar classe vazia e reamostrar a paleta (`cores[round(i*(L-1)/(k-1))]`).
   Teste deve afirmar `classe(0)` e que a cor máxima é usada.
2. `mapa.ts:260` / `escalas.ts:54` NaN/±Infinity: no `step` do MapLibre caem na classe 0, na escala D3
   viram "sem dado". Filtrar com `Number.isFinite` em `aplicarValores`, `valoresPorNivel` e tabela. Teste com NaN.
3. `mapa.ts:155,216,241` custo com ~5.570 municípios: `features.find` dentro do `sort` (O(n² log n)) e
   tabela de ~28k nós recriada a cada troca. `Map<id,nome>` + `Intl.Collator` uma vez; ids ordenados em
   cache; tabela preenchida só no `toggle` do `<details>`.
4. `mapa.ts:204-205` `mousemove`: se o id destacado não mudou, só reposicionar o tooltip.
5. `mapa.ts:229-231` teclado: `keyboard: false` no `Map`, `focusout` em vez de `blur`, um único focável;
   e2e com foco no canvas.
6. Teste enganoso `mapa.spec.ts:47-51`: criar/destruir 20× e afirmar ausência do aviso
   "Too many active WebGL contexts".
