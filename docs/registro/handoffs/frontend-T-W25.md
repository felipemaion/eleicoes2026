# Handoff frontend — T-W25 (cabeçalho compacto no celular)

Branch `fix/frontend-cabecalho-mobile` (a partir de `origin/main`). Descartei antes os PNGs T-W12/T-W20 regenerados.

## O que mudou (≤ 768 px; desktop inalterado)
- Barra única de 56 px, fixa: selo "14" + "Eleições 2026", botão Buscar (ícone) e botão ☰ (`aria-label` "Menu").
- ☰ abre painel com as 7 abas e "Tema claro" dentro. Fecha ao escolher, com Esc (devolve o foco ao ☰) e ao tocar fora; foco preso enquanto aberto; `aria-expanded`/`aria-controls`.
- Busca: o ícone abre o campo por cima da barra (foco automático); 1º Esc fecha as sugestões, 2º fecha o campo.
- Filtros (< 1024 px): o botão "Filtros: cargo · UF · ano" já existia; agora o painel flutua sobre o conteúdo (não empurra a página), fecha com Esc e ao tocar fora.
- Sem rolagem horizontal. Código novo em `src/componentes/ui/cabecalho-movel.ts`; `main.ts` monta o painel (`div.menu-painel`, `display: contents` no desktop); CSS no fim de `estilo.css`.

## Decisões
- Menu em painel (alternativa de abas roláveis descartada: 7 rótulos longos não cabem e a aba ativa some).
- Breakpoint 768 px para cabeçalho; filtros em painel flutuante até 1024 px (onde a lateral vira coluna fixa).

## Verificar
`cd apps/web && pnpm lint && pnpm test && pnpm exec playwright test` (cabecalho-movel.spec.ts cobre 390×844 e 768×1024 + desktop; unit `cabecalho-movel.test.ts`). Resultado: lint/tsc/369+ unit/e2e verdes.

## Capturas (390×844)
Antes: `img/T-W25-antes-390.png` · Depois: `img/T-W25-depois-390.png`, `-depois-menu-390.png`, `-depois-busca-390.png`, `-depois-filtros-390.png`.

## Pendências
Nenhuma. Os T-W23 modificados e T-W16 não rastreado em `img/` são resíduos antigos, não tocados.
