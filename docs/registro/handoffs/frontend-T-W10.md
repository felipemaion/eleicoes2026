# Handoff frontend — T-W10 (redesenho visual Missão)

Branch `feat/frontend-redesenho`. Capturas antes/depois (360/1280/1920, visão geral e mapa) e dos tooltips em `docs/registro/handoffs/img/T-W10/`.

## O que foi feito
- **Identidade**: cores lidas do CSS do site oficial (https://missao.org.br, 08/10/2026): amarelo `#fcbe26`, preto `#070d0c`, branco. Constantes em `OFICIAL_MISSAO` (`src/paletas.ts`). Tema **escuro por padrão**; claro opcional pelo botão do topo (lembrado em localStorage; `data-tema="claro"`). Tokens novos: `acento`, `texto-acento`, `superficie-alta`, `dado`. `destaque` (texto/linha/foco) é amarelo no escuro e âmbar `#8a4f00` no claro (≥ 4,5:1) — amarelo nunca é texto sobre branco.
- **Paletas de dados** derivadas da marca: sequencial creme→âmbar-queimado (7 classes, luminância monotônica), divergente âmbar↔azul com neutro creme, categórica Okabe-Ito mantida. Densidade (heatmap/círculos) em azul para não se confundir com o coroplético amarelo. Mesmas quebras 2022/2026 (a escala não mudou).
- **Layout**: topo fixo (marca, nav, tema); filtros em painel lateral fixo (≥ 1024 px) ou faixa compacta no mobile; conteúdo usa toda a largura; mapa ocupa a altura útil (`100dvh - 20rem`) com painel do município ao lado (colapsa < 1100 px). Sem rolagem horizontal em 360/768/1280/1920 (teste e2e).
- **Carregando**: `componentes/ui/sobreposicao.ts` — overlay em tela cheia, `role=status`, `aria-busy` no `<main>`, só aparece após 200 ms e fica ≥ 250 ms. `carregar()` e a tela do mapa o usam; o conteúdo reserva espaço (`.reserva-carga`). Erros seguem inline, com borda destacada e botão amarelo "Tentar novamente".
- **Tooltips**: `componentes/ui/tooltip.ts` + `posicionamento.ts` (puro, testado): fundo sólido, seta, vira para cima, nunca sai da tela, hover/foco/toque, Esc (inclusive só com mouse — WCAG 1.4.13). Usado no "?" (`ajuda()`), nas barras do ranking e no mapa.
- **Ranking**: margem esquerda calculada pelo nome mais longo (até 38%) + quebra em linhas (`quebrarLinhas`); nada é cortado. Tooltip da barra: nome de urna, partido (nº), UF, cargo, resultado, votos.
- Hover consistente: KPIs, barras, linhas de tabela, botões, links de navegação.

## Verificação
`pnpm lint && pnpm typecheck && pnpm test` (189 testes) e `pnpm test:e2e` (39 passam; inclui axe WCAG 2.2 AA nas 6 telas + `redesenho.spec.ts`). Lighthouse a11y (visão geral, build de produção, API fora do ar → estado de erro): **100**.

## Decisões / pendências
- **Nome civil**: o contrato `CandidatoResumo` só traz `nm_urna`; o tooltip mostra o nome de urna. Pedir ao backend `nm_candidato` (nome civil) no contrato para completar o item 5 do brief.
- Tema claro: a classe mais clara do sequencial (creme) fica próxima do fundo do mapa; a separação vem das bordas dos polígonos (documentado no teste de paletas).
- Corrigi dois e2e que dependiam de `data/processed/tiles` local (agora interceptam `/tiles/manifesto.json` → 404 ou usam `select[name=uf]`); falhavam só em máquina com tiles gerados.
- T-W11 mexe nos filtros: o painel lateral já está pronto para recebê-los (`.lateral`).
