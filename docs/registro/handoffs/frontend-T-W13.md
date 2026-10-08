# Handoff frontend — T-W13 (verificação final em produção + acabamento)

Branch `fix/frontend-acabamento` (a partir de `origin/main` @897232d, T-B11 incluso). Capturas em
`docs/registro/handoffs/img/T-W13/` (1440 e 390 px; `item<N>-…`). Verificação reproduzível:
`E2E_PROD=1 pnpm exec playwright test producao --config=playwright.prod.config.ts`
(`E2E_BASE=http://localhost:4173` aponta o mesmo roteiro para um `vite preview` local com `API_ALVO` = produção).

**Como ler a coluna "onde":** *prod* = verificado na produção como está hoje; *local+prod-API* = o código novo
deste PR, servido localmente contra a API de produção (só entra em produção após merge e deploy).

| # | Pedido | Status | Onde / evidência |
|---|---|---|---|
| 1 | Nomes completos no ranking | **corrigido** | Em prod o começo do nome era cortado ("3. MARCELO BRIGADEIRO" saía como "ARCELO…"): a margem usava 6,6 px/char, mas nomes de urna são CAIXA ALTA (~8,2 px). Agora `larguraEstimada` por caractere. local+prod-API · `item1-ranking-*` |
| 2 | Mapa de presidente carrega (Brasil todo; exterior à parte) | ok | prod · `item2-mapa-presidente-*` ("Votos no exterior: 8.580 (fora do mapa)") |
| 3 | Gastos: hover/foco/toque com tooltip completo, % público vindo de `/gastos` | **corrigido** | `pontosDeGastos` não junta mais com `/candidatos` (some uma chamada de 500 itens); Partido, Resultado e **% recursos públicos** vêm do `/gastos`. Em prod hoje o balão ainda não tem a linha % (deploy pendente). local+prod-API · `item3-gastos-hover-*`; foco por teclado coberto no teste |
| 4 | "?" e "fonte" legíveis/bonitos; chip não quebra linha | **corrigido** | chip "fonte" foi para linha própria no cartão; o "?" fica colado à última palavra do rótulo (`.kpi-fim`); painel da fonte quebra o texto longo da regra sem transbordar. local+prod-API · `item4-ajuda-*`, `item4-fonte-*` |
| 5 | Tela toda, responsivo, paleta Missão | **corrigido** | prod já usava a largura toda e a paleta (`--cor-destaque #fcbe26` sobre preto), sem rolagem horizontal. No celular os filtros ocupavam a 1ª tela inteira: agora recolhem num botão-resumo ("Filtros: Governador · RJ · 2026 ▾"), só < 64rem. local+prod-API · `item5-layout-*` |
| 6 | "Carregando" em overlay de tela cheia | ok | overlay cobre exatamente 1440×900 / 390×844 (teste mede o `boundingBox`) · `item6-overlay-*` |
| 7 | Nada de "Não foi possível carregar…" nos casos válidos | ok | **prod**: Renan Santos, Kim, Guto Zacarias, Capitão Contar (senador), Coronel Busnello (governador RJ) e deputado estadual PE × 5 telas × 1440/390 = 60 combinações, 0 alertas. Só o Renan tem captura no repositório (`item7-*-renan-*`); os demais provam-se pelo teste |
| 8 | Filtros dependentes (`/candidatos/ufs`) + busca global com sugestões | **corrigido** | UF só lista estados com candidatura no cargo (governador do Missão: 9 UFs + Brasil, em vez de 28); UF sem candidatura volta a Brasil; deep-link só com `cand=` ajusta cargo/UF/ano/grupo ao candidato sem redesenhar a tela (`store.ajustar`). A busca pedia 8 itens e a API não ordena por relevância (Renan Santos, 2,6 mi de votos, ficava fora dos 8 primeiros de 56): agora pede 40 e ordena (nome começa pela consulta → mais votos → 2026). local+prod-API · `item8-*`, `item8b-*` |
| 9 | Mapa só com a região do candidato | ok | prod: presidente → país (`data-abrangencia='pais'`), deputado estadual PE → `PE` · `item9-mapa-estadual-*` |
| 10 | Evolução: escolher/buscar/filtrar candidatos (`pessoas=`) | **pendente (backend)** | A UI está pronta (busca por nome, "só indicados", marcar e "Comparar selecionados"), mas **`GET /api/evolucao/pessoas` devolve `total: 0` em produção para qualquer filtro** (`?q=guto`, `?cargo=DEPUTADO FEDERAL&uf=SP`, sem filtro) — a lista fica vazia ("Nenhuma pessoa encontrada"). `/comparativo?comparacao=evolucao_missao` funciona. Precisa do backend. `item10-evolucao-*` |
| 11 | Ficha: total gasto, links oficiais (verificado/nota) e "fonte" por número | ok | prod: 14 links `tse.jus.br`, 5 botões "fonte", bloco de gastos completo · `item11-ficha-*` |
| 12 | "Todos os cargos" na Visão geral nunca engana | ok | Não existe opção "todos": o cargo é sempre enviado e `store.ts` documenta o porquê. Nada a mudar |

## O que mudou (código)
- `/candidatos/ufs`: `cliente.ufs`, tipo `RespostaUfs`, `opcoesDeUf(consulta, disponiveis)`, filtros dependentes (`filtros.ts`).
- `store.ajustar` + `telas/recorte.ts` (`seguirCandidato`): recorte dos filtros segue o candidato aberto (mapa e ficha); a lista do seletor da ficha usa o recorte do candidato.
- `gastos-logica.pontosDeGastos(g, base)` e `telas/gastos.ts`: só `/gastos`.
- `busca-logica.ordenarSugestoes`, `LIMITE_BUSCA=40`, `MAX_SUGESTOES=8`.
- `barras.larguraEstimada`; `kpi.ts` (chip fonte em linha própria, `.kpi-fim`); botão de filtros no celular (`main.ts`, `estilo.css`).
- `api.d.ts` regenerado do OpenAPI atual (estava defasado: sem `/candidatos/ufs` e sem partido/resultado/%público em `/gastos`); fixtures `ufs.json` e `gastos.json` atualizadas.
- Roteiro de produção: `tests/e2e/producao.spec.ts` + `playwright.prod.config.ts` (fora do CI: `E2E_PROD=1`).

## Pendências / para o orquestrador
1. **Backend:** `/evolucao/pessoas` vazio em produção (item 10). Sem isso a Evolução só compara o grupo inteiro.
2. **Backend (sugestão):** `/busca` não ordena por relevância/votos; o front compensa pedindo 40 itens, mas ordenar no servidor é o certo (e permitiria `limite=8` de novo).
3. **Deploy:** itens 1, 3, 4, 5 e 8 só aparecem em produção depois do merge/deploy deste PR; verificados localmente com a API de produção.
4. A API já expõe os grupos `mbl_2026` e `mbl_2022_indicados` (em `/meta`), que o seletor "Grupo comparado" ainda não oferece (`GRUPOS` no store tem só `missao_2026` e `mbl_2022`). Fora do escopo de T-W13; vale um brief.

## Como verificar
```bash
cd apps/web && pnpm exec tsc --noEmit && pnpm exec eslint src tests && pnpm exec vitest run   # 292 testes
pnpm exec playwright test                                                                      # 57 (mock), 89 fora do CI
E2E_PROD=1 pnpm exec playwright test producao --config=playwright.prod.config.ts               # contra produção
```
