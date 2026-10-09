# Handoff frontend — T-W24 (aba Redes sociais)

Branch `feat/frontend-redes-sociais` (sobre `origin/main` e5cadd4; **sem push**). Rota `#/redes`, item "Redes sociais" na navegação.

## O que foi feito
- Tipos regenerados do OpenAPI (`pnpm gen:api`); cliente com `redes`, `redesCorrelacoes`, `redesSerie`.
- `dados/redes-logica.ts` (puro, 18 testes): frase-resumo, KPIs, ρ de Spearman em palavras (+ IC, n, "não prova causa"), classe acima/abaixo do esperado (≥1,5× / ≤0,67×), rankings top 10, busca, status do perfil, ritmo por janela, série (1 ponto vs linha).
- Dispersão seguidores×votos: `dispersao.ts` generalizado (formatoX, rótulo do eixo, `reta` log-log, `linkExterno`, `classe`); clique abre o Instagram; eixos log só com ticks 1/2/5 (corrige rótulos sobrepostos).
- Novos gráficos: `ritmo.ts` (antes/durante/depois: mediana do grupo × candidato; janela sem taxa mostra "n/d", não zero) e `serie-tempo.ts`. Todos com tabela alternativa e tooltip da T-W23.
- Candidato em foco por busca (sem listas longas); perfil indisponível aparece como "Perfil indisponível" + motivo + link do TSE; sem chamada de série.
- 503 (`redes_indisponiveis`) e 422 (grupo de 2022) viram aviso claro, não "tente de novo".
- Textos do `textos.json`. `textos.ts` ganhou `{dt_coleta_redes}` (data de Brasília), filtro dos avisos de redes pelos ids da API e `redes_segundo_turno` só para presidente/governador. Fonte do Instagram via `fonteRotuladaUi` (usa o `rotulo` da API).
- Fixtures `redes*.json` (14 candidatos SE, 4 sem número; série de 1 e 2 pontos), tipadas contra o OpenAPI.

## Verificação
`cd apps/web && pnpm lint && pnpm tsc --noEmit && pnpm vitest run` (366 ok) · `pnpm playwright test` (75 ok, axe WCAG 2.2 AA incluindo `#/redes`).
Capturas: `docs/registro/handoffs/img/T-W24-redes-{desktop,indisponivel,mobile}.png`.

## Pendências
- Em produção os endpoints respondem 503 até `make publicar-dados` + redeploy (handoff do backend).
- Busca da aba rotulada "Escolher candidato em foco" (o global já usa "Buscar candidato").
- Datasets da fonte: `redes_perfis` (Instagram) e `rede_social_candidato` (TSE).
- A suíte e2e com `SALVAR_CAPTURAS=1` regenerou PNGs de outras tarefas (T-W12/W20/W23) e criou `T-W16-financiamento.png` no working tree; **não entraram no commit** — descarte com `git checkout -- docs/registro/handoffs/img` e apague o T-W16 novo.
