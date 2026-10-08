# Handoff frontend — T-W20 (Evolução 2022×2026: comparador claro)

## O que mudou
- **Frase-resumo** no topo (`.frase-resumo`, `aria-live`): "Comparando **X** (2022) com **Y** (2026) · cargo · UF — N candidaturas → M candidaturas" (n_de/n_para da API).
- **Dois cartões 2022 → 2026** (`telas/comparador-cartao.ts`), empilhados no mobile. Cada um: o que está escolhido em uma linha + "Alterar" → alternância **Grupo** (select só com os grupos do ano) | **Candidatos** (busca com combobox, foto, ≤ 8 sugestões, chips removíveis, limite 10 por lado). "Limpar" volta ao padrão.
- **Lista longa removida** (`evolucao-selecao.ts`, `evolucao-tabela.ts`, `dados/evolucao-logica.ts` apagados; `/evolucao/pessoas` não é mais chamado). O seletor "Comparar" também saiu: os grupos configurados são opções dos cartões. Sem atalho "mais votados" (a API não ordena por votos na busca).
- Abaixo: KPIs rotulados "Penetração em 2022/2026" com o nome do lado, três mapas, tabela "Candidaturas escolhidas" (só quando há lado de candidatos; vem das fichas), e **"Notas sobre os dados"** recolhidas.
- **Estado na URL**: `#/evolucao?de=c:301,302&para=g:missao_2026` (`g:<grupo>` | `c:<sq>,<sq>`; vazio = padrão; lixo é descartado). `store.Filtros.pessoas` virou `de`/`para`.
- **Parâmetros** (`dados/comparador-logica.ts`, `paramsComparativo`): dois grupos de uma comparação declarada → `comparacao=`; senão por lado `grupo_2022|2026` / `sq_2022|2026` (misto funciona, T-B15). Nunca envia `mesmos_candidatos` (T-B16).
- **422**: `cliente` agora lança `ErroApi {status, codigo}`. `sq_fora_do_recorte` → mensagem no cartão do(s) lado(s) de candidatos (`.cartao-erro-api`, role=status); demais 422 → mensagem curta no lugar do resultado; os cartões continuam.
- **Indicados (item 9)**: selo "indicado MBL" nas sugestões e chips (campo `indicado`); no cartão 2022 os grupos `mbl_2022_indicados` e `mbl_2022` ganham nota com os quatro nomes e o critério.

## Decisões / pendências
- Textos novos estão em `src/telas/textos-comparador.ts`: `docs/metodologia/publico/textos.json` e o README público são do analista. **Pendente com o analista/orquestrador:** (a) mover os textos para `textos.json`; (b) **entrada de glossário em "Como ler este painel"** (README público) — "indicados" = 4 candidaturas de 2022 indicadas pelo MBL (Kim Kataguiri, Guto Zacarias, Renato Battista, Cristiano Beraldo; `origem=indicado` em `data/reference/mbl_2022.csv`); grupo MBL 2022 = indicados + candidatos do Missão 2026 que disputaram 2022. Os nomes na nota do cartão estão fixos no texto (não vêm da API).
- 422 por lado: o corpo do erro não traz qual lado falhou; mostro nos dois lados de candidatos.
- `src/dados/gerado/api.d.ts` **não** foi regenerado: regenerar quebra `gastos.ts`/`candidato.ts`/fixtures (T-B14: `receitas` agora anulável). A tela usa `Params` genéricos, então não depende disso. Regenerar é tarefa à parte.
- Fichas dos candidatos escolhidos são buscadas (nomes dos chips ao recarregar a URL e tabela): até 20 chamadas no pior caso.

## Verificar
`cd apps/web && pnpm exec vitest run && pnpm build && pnpm exec playwright test` (321 + 65 verdes; eslint e tsc limpos).
E2E `tests/e2e/comparador.spec.ts`: Guto 2022 × Rafa 2026 (dep. estadual SP), Kim + Beraldo 2022 × Missão 2026 inteiro (dep. federal SP), recarregar a URL, nenhuma lista > 8 itens, sem rolagem horizontal no mobile, 422.
Capturas: `docs/registro/handoffs/img/T-W20-guto-rafa-desktop.png`, `T-W20-kim-beraldo-missao-desktop.png`, `T-W20-kim-beraldo-missao-mobile.png`.
