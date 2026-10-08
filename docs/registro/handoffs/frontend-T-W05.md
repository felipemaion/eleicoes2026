# Handoff — frontend T-W05 (OpenAPI real, PMTiles, painel do município, textos públicos)
Branch `feat/frontend-integracao`, empilhada sobre `feat/frontend-telas` (PR #36 — **integrar #36 primeiro**).
3 commits: corridas (item 0) · contrato real + painel + manifesto de tiles · textos públicos + e2e.

## O que foi feito
- **Item 0 (revisão do PR #36).** `painel-mapa.mostrarPontos` com `seqPontos` conferido depois do `await`, inclusive no ramo `null` (desligar densidade); `mapa.ts` confere `seq` também no `catch` (erro de resposta velha não cobre mapa válido); resumo do município com `seqMun`. `AbortSignal` como último argumento de **todos** os métodos do `ClienteApi`; requisições antigas são abortadas (`foiCancelada` não vira alerta). Testes de corrida em `telas.test.ts` (fetch controlável).
- **Item 1 — tipos do OpenAPI.** `contrato.ts` agora só reexporta `components["schemas"]` (nada escrito à mão) + `QueryDe<path>`. Fixtures `tests/fixtures/api/*.json` reescritas no formato real e **tipadas pelo compilador** em `contrato-fixtures.test.ts` (`satisfies`): renomeou campo no backend → `pnpm typecheck` quebra. Cliente/adaptadores/telas migrados.
- **Item 3 — PMTiles.** `src/dados/tiles.ts` lê/valida `/tiles/manifesto.json` (`cache: no-cache`); `mapa-embutido.ts` usa `municipios` (todas as UFs) e `zonas_<ano>`; **404 do manifesto = sem tiles → cai na fixture de Sergipe com aviso** (outro erro falha alto). Nível "Zona" só habilita com camada `zonas_<ano>` **e** UF escolhida (a API exige `uf` fora do município). `servir-tiles.ts` (plugin Vite, dev e preview) serve `data/processed/tiles` em `/tiles/` com Range; produção é o Caddy.
- **Item 4 — painel do município.** `Mapa` ganhou `aoSelecionar(id, nivel)`: clique **ou Enter/Espaço** na área destacada pelo teclado. Painel `aside` (`aria-live`) com tabela por grupo/cargo; foco vai ao `h2`. Chave de zona (`IBGE-zona`) abre o município. O seletor "Resumo do município" saiu (a API do mapa não manda nomes).
- **Item 5 — textos públicos.** `textos.json` importado no build (`src/textos.ts`: placeholders `{dt_geracao}`/`{mes_base_ipca}`, avisos por tela, glossário); `textos-ui.ts`: botão **"?"** (aria-expanded/controls, Esc fecha), banners, subtítulo, rodapé. KPIs aceitam `ajuda`. Nova tela **"Como ler este painel"** (`#/como-ler`) renderiza o `README.md` por `markdown.ts` (DOM, sem `innerHTML`; tabelas, listas, links externos).
- **Item 6.** Proxy `/api → :8000` já existia; `fs.allow` liberado para `docs/`.

## Divergências do contrato real (backend é a verdade)
| Tema | Provisório | Real | Tratamento |
|---|---|---|---|
| Unidades | fração 0–1 | **penetração em ‰**, % válidos/públicos em **0–100** | `formatarPermil/Pontos`, `formatadorDaUnidade(unidade da API)`; KPI `permil`/`pontos` |
| Cargo | `deputado_federal` | enum `DEPUTADO FEDERAL`; **/mapa e /comparativo exigem cargo** | `cargoDaApi`; "Todos" vira deputado federal **com aviso na tela** |
| /candidatos | `candidatos`+`kpis`+`indicado` | `itens`, `total`, **sem KPIs agregados, sem `indicado`** | KPIs derivados (soma/contagem) + /gastos; "só indicados" **removido** |
| /mapa | `nome`, `escala_sugerida` string, `extensao` | `escala_sugerida{tipo,quebras,aviso}`; **sem nomes**; valores podem ser `null` | `escalaLimiar(quebras da API)`; `null` = "sem dado"; nomes vêm dos tiles (`properties.nome`) |
| Indicadores do mapa | penetração, %válidos, LQ, swing | `penetracao`, `pct_validos`, `votos` | seletor só com as 2 taxas; votos = densidade (pontos); swing/LQ saem do mapa |
| /mapa/pontos | — | exige `uf`; paginado (`truncado`) | densidade desligada no Brasil inteiro |
| /comparativo | `candidatos` por par, `penetracao_antes/depois`, `mes_base_deflator` | `municipios[]` por **`cd_amc`** com `penetracao_de/para`, `kpis`, `de/para`, `mesmos_candidatos`; **sem comparação por candidato** | gráfico por candidato **removido**; mapas montados dos `municipios[]` |
| /gastos | `candidatos`, `receita_por_fonte` | `agregado`, `receitas.por_categoria`, `por_candidato`, `base_ipca` | 1 barra "Total do grupo"; aviso do IPCA vem do texto público |
| /municipios | `aptos`, `grupos[].taxa` | `grupos[].cargos[]` | tabela por cargo |

## Pendências / pedidos (via orquestrador)
1. **Quebras comuns 2022+2026 (item 2): NÃO atendido.** O OpenAPI na main (T-B02) não traz quebras comuns em `/mapa` nem `/comparativo` (o backend usa quintis da própria resposta — TODO T-A06 em `mapa.py`). A Evolução segue calculando quantis de 2022∪2026 no cliente (mesma escala nos 2 mapas); a tela Mapa usa as quebras da resposta. **Pedir ao `backend`**: `escala_sugerida.quebras` comuns aos dois anos (e no `/comparativo`).
2. **Chave do mapa de evolução é `cd_amc`**, mas a geometria é por `cd_mun_ibge`. Só casa se `cd_amc` = código IBGE do município representante; AMCs agregadas não terão polígono. **Pedir ao `dados`** (T-D04): camada por AMC (ou propriedade `cd_amc` nos polígonos).
3. **Formato do `tiles/manifesto.json` não estava especificado** — implementei e peço ao `dados` que gere assim (o front valida e falha alto):
   `{"camadas": {"municipios": {"arquivo":"municipios.<hash>.pmtiles","camada":"municipios","id":"cd_mun_ibge","limites":[oeste,sul,leste,norte]}, "zonas_2026": {..., "id":"<chave IBGE-zona>"}}}`. As feições precisam de `properties.nome` (tooltip e ordem do teclado).
4. Backend: **KPIs agregados por grupo** (penetração e % válidos do grupo — hoje só soma/contagem/custo/% público); `indicado` por candidato; `nome` em `/mapa.detalhes`.
5. Aviso `n_baixo` (hachura) **não é exibido**: o mapa ainda não hachura (não prometer o que não existe).
6. Caddy (agente Oracle): servir `/tiles/` com `Accept-Ranges`, `Cache-Control: immutable` nos `.pmtiles` e `no-cache` no manifesto. Nenhum tile real foi testado (não existem); testado: parsing, URL, Range e fallback.
7. Lighthouse/axe **não foi reexecutado** nas telas novas (banners, "?", Como ler); a semântica seguiu o padrão da T-W04.

## Como verificar
```bash
cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:e2e
E2E_API_REAL=1 pnpm test:e2e api-real   # opcional: API real em :8000 (make dev)
```
Local: 163 testes Vitest, 19 Playwright (+2 do `api-real`, pulados sem a API), lint/tsc limpos.
Cuidado: `playwright.config` usa `reuseExistingServer`; um `vite preview` antigo na :4173 serve build velho (aconteceu aqui — encerrei o processo).
