# Handoff — analise · T-A09 (textos do comparador e glossário "indicados")

Branch `docs/analise-textos-comparador` (a partir de `origin/main` 3a78377). Commits:
`test(metodologia): …` (vermelho) → `docs(metodologia): …` (verde). `make lint test` verde
(py 662 passed; web 31 arquivos / 313 testes).

## O que foi feito
1. **Glossário** (`textos.json › glossario`, exibido em "Como ler"): novas entradas `indicados`,
   `grupo_mbl_2022`, `grupo_mbl_2026`, `comparador`.
2. **README público** (`docs/metodologia/publico/README.md`): seções "O comparador" e
   "Indicados e grupos" (substitui "Quem está no grupo MBL 2022").
3. **Textos do comparador** passam a viver em `textos.json › comparador` (fonte única), revisados:
   - `comparador.placeholders`: `{busca}`, `{n}`, `{total}`, `{contexto}` (locais, só desta seção;
     o teste impede que vazem para outras seções).
   - `comparador.ui`: strings da interface.
   - `comparador.nota_grupo`: nota por id de grupo (`mbl_2022_indicados`, `mbl_2022`, `mbl_2026`,
     `missao_2026`).
4. `telas.evolucao.subtitulo` reescrito para o comparador (lado 2022 × lado 2026, grupo ou
   candidatos, mesmo cargo e UF).
5. Testes (`test_textos_publicos.py`) amarram os textos ao `data/reference/mbl_2022.csv`: os 4
   nomes com `origem=indicado` aparecem no glossário e na nota; "18 candidaturas" = nº de linhas;
   quem está fora do Missão em 2026 (Beraldo, PP) aparece em `grupo_mbl_2026`.

## Chaves para o frontend (troca de `TEXTOS_COMPARADOR` em `textos-comparador.ts`, T-W20)
| TS (antes) | `textos.json › comparador.ui` | mudança de texto |
|---|---|---|
| alterar / aplicar / cancelar | alterar / aplicar / cancelar | — |
| limpar | limpar | "Voltar ao padrão" |
| modoRotulo / modoGrupo / modoCandidatos | modo_rotulo / modo_grupo / modo_candidatos | — |
| grupoRotulo | grupo_rotulo | — |
| buscaRotulo | busca_rotulo | — |
| placeholderBusca | placeholder_busca | "Nome, número ou partido" (aceita número) |
| sugestoesRotulo | sugestoes_rotulo | — |
| minimo | minimo | "…2 letras ou números." |
| buscando | buscando | — |
| buscaIndisponivel | busca_indisponivel | reescrito |
| semResultado(q) | sem_resultado com `{busca}` | — |
| refine(n,total) | refine com `{n}`, `{total}` | "Mostrando {n} de {total} resultados. Digite mais para refinar." |
| erro422 | erro_422 | diz qual é o problema e onde mudar |
| erroSqForaGeral | erro_sq_fora_geral | ajustado |
| erroSqLado | erro_sq_lado | — |
| seloIndicado | selo_indicado | "indicado pelo MBL" |
| notaGrupo[id] | `comparador.nota_grupo[id]` | + `mbl_2026` (Beraldo/PP) e `missao_2026` |
| carregandoNomes / notasDados / tabelaTitulo | carregando_nomes / notas_dados / tabela_titulo | — |
| *(literal em evolucao.ts)* "Sem dados comparáveis…" | sem_dados_comparaveis | novo |
| *(literal em evolucao.ts)* `Recorte: ${contexto}…` | recorte com `{contexto}` | novo |

Placeholders do comparador: troca simples `replaceAll("{busca}", q)` etc. (não passam por
`preencher()`, que só conhece `{dt_geracao}`/`{mes_base_ipca}`).

## Pendências / sugestões
- Frontend: importar de `textos.json`, apagar `textos-comparador.ts`, e mostrar o termo do
  glossário (`indicados`) ao lado do selo — é a resposta direta ao "onde o usuário vê isso?".
- Ainda há literais de UI em `evolucao.ts` (rótulos dos KPIs, legendas dos mapas). Se quiserem,
  migro numa tarefa própria.

## Como verificar
`make lint test`; `uv run pytest packages/indicadores/tests/test_textos_publicos.py -q`.
