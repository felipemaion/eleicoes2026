# Handoff frontend — T-W27 (clique na nuvem seguidores × votos seleciona o candidato)

- **Branch:** `feat/frontend-redes-clique-seleciona` (de `origin/main` 79da584) · **Issue:** #103
- **Commits:** `test(web): …` (vermelho, f41b256) → `feat(web): …`

## O que mudou
- `componentes/graficos/dispersao.ts`: opção **opt-in** `aoSelecionar(id)`. Com ela, clique/Enter/Espaço no
  ponto chama `aoSelecionar`, **fixa** o tooltip junto do ponto (classe `fixo`, `role="dialog"`) e põe o
  `linkExterno` como `<a target="_blank" rel="noopener noreferrer">` (`linkExterno.texto`, campo novo e
  opcional). O clique não abre mais o link direto nesse modo. Sem a opção, nada muda (Gastos/Receitas
  seguem com `role="link"` e clique abrindo o TSE — teste de regressão).
  - Comportamento igual ao de `ligarPainel`: segundo clique no mesmo ponto, Esc ou clique fora fecham;
    clique em outro ponto troca seleção e balão; hover/mousemove/blur não mexem no balão fixo
    (balão de hover "guardado").
  - Teclado: ponto `role="button"`, `aria-expanded`, `aria-controls`; Tab no ponto fixado leva ao link;
    Shift+Tab no link volta ao ponto; Tab no link fecha e segue ao próximo ponto; Esc devolve o foco ao
    ponto sem reabrir o balão de hover.
  - Só `https://` vira link (mesma regra de `abrirNoTse`).
- `telas/redes.ts`: `selecionarFoco(candidato)` único, usado pela busca e pelo clique (DRY); o candidato vem
  de `redes.candidatos` pelo `sq_candidato`. Convite do hover e nota abaixo do gráfico descrevem o novo
  comportamento.
- `estilo.css`: borda mais grossa no balão fixo; estilo/foco visível do link.
- `ui/tooltip.ts`: não precisou mudar.

## Testes
- Unit (`graficos.test.ts`): seleção + link, persistência do fixo, troca/clique fora/Esc, teclado, regressão TSE.
- Unit (`telas-redes.test.ts`): clique no ponto → campo de busca, cartão, realce, série (`sq=6`), ritmo, balão com link, nota.
- E2E (`redes.spec.ts`): clique → foco + balão fixo + link `_blank`; hover no link não fecha; Esc fecha.
  O teste da busca passou a escopar o botão em `.busca-redes-resultados` (os pontos agora também são botões com o nome).

## Como verificar
```bash
cd apps/web && pnpm exec tsc --noEmit && pnpm exec eslint src tests && pnpm exec vitest run && pnpm exec playwright test
```
Resultado local: 397 unit, 92 e2e passando; tsc/eslint limpos.

## Pendências
Nenhuma.
