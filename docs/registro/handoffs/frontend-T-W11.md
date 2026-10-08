# Handoff — frontend T-W11 (filtros e busca intuitivos; mapa focado no candidato; presidente)

Branch `feat/frontend-filtros-busca` (a partir de `origin/main` = T-W10 #56). Só `apps/web/` e este arquivo.

## O que foi feito
1. **Busca global** (`componentes/busca/`): combobox ARIA 1.2 no topo, atalho `/`, debounce 200 ms, mín. 2 caracteres,
   cancela chamada anterior, destaque do trecho (sem acento/caixa), linha "ano · cargo · UF · partido (nº) · votos".
   **Enter** abre a ficha; **Shift/Ctrl+Enter** (ou Shift+clique) fixa no mapa. Vazio e falha têm mensagem própria na
   própria busca (nunca o erro genérico da tela). Núcleo reutilizável em `componentes/ui/combobox.ts`.
2. **Filtros** (`componentes/filtros/`): ano e cargo viram chips (rádios), UF é combobox com busca por nome/sigla,
   grupo com descrição curta, contagem ao vivo (`/candidatos?limite=1`, debounce 250 ms, `aria-live` sem `role=status`),
   "Limpar filtros" (some quando já é o padrão). Presidente força Brasil e trava a UF (regra em `filtros-logica.ts`,
   aplicada no store). Tudo continua no hash (deep-link).
3. **Mapa por candidato**: `filtros.candidato` (`cand=ano:sq`) agora comanda o mapa. Ano/cargo/UF vêm da **ficha**
   (`abrangencia`), nunca dos filtros da tela (esse era o bug do Renan: UF/cargo de outro recorte). `Mapa.definirAbrangencia`
   enquadra a UF (ou o país) e esmaece o resto (`expressaoOpacidade`, prefixo IBGE de 2 dígitos). Faixa "Mostrando só onde
   disputou: …" + "Ver o grupo todo". Mesmo tratamento no mapa da ficha. O enquadramento é aplicado **antes** de colorir, então
   `data-mapa-pronto=sim` já implica região à vista; `data-abrangencia` (SE/…/`pais`) é o gancho de teste.
4. **Presidente**: mapa nacional carrega; `votos_fora_do_mapa` aparece como "Votos no exterior: N (fora do mapa)."
5. **Erros**: ficha/mapa de Renan Santos, Kim, senador e deputado estadual testados com mock (e2e) **e contra a API real**
   (`api-real.spec.ts`, 4 candidatos + busca). A ficha também funciona quando o candidato não está na lista do recorte.
6. **Correções da T-W10**: avisos compactos (`avisosUi`: o essencial à vista + `<details>` "Notas sobre os dados (N)");
   **não existe mais "Todos os cargos"** — somar presidente + deputados dá número sem sentido; o padrão é **deputado federal**
   (hash antigo `cargo=todos` cai no padrão). Os KPIs do grupo usam `kpis` da API quando vêm (exatos), senão a soma dos itens
   (rotulada como parcial se truncada).

## Decisões
- "Todos" removido em vez de somar por cargo (a API já devolve `kpis: null` sem cargo pelo mesmo motivo).
- Busca é global por padrão (não restringe aos filtros); `paramsDaBusca(..., restringir)` já suporta restringir.
- Fixtures do contrato atualizadas para o OpenAPI atual (`abrangencia`, `kpis`, `votos_fora_do_mapa`, `busca.json`);
  `tests/fixtures/api/tipado.ts` estreita o enum `abrangencia.tipo` que o JSON alarga para `string`.
- `vite.config.ts`: `API_ALVO` (env) escolhe o alvo do proxy de dev/preview (padrão `localhost:8000`).
- `src/dados/gerado/api.d.ts` regenerado (`pnpm gen:api`) — estava defasado em relação ao OpenAPI da T-B07.

## Pendências / limites
- "Cargo restringe as UFs com candidatos" **não** foi feito: exigiria endpoint de UFs por cargo (ou baixar a lista). Hoje
  a contagem ao vivo mostra "Nenhuma candidatura…" quando o recorte é vazio. Sugestão ao backend: `GET /api/candidatos/ufs?cargo&ano&grupo`.
- A API em `:8000` do worktree do backend estava defasada (sem `/busca`, ficha do presidente 500); verifiquei contra uma API
  nova do worktree `frontend` em `:8001` (`ELEICOES_DIR_DADOS=…/.worktrees/dados/data/processed`). Reinicie a de `:8000`.
- Sem PMTiles do Brasil em dev o mapa usa a geometria de demonstração (SE); com tiles, o fit/esmaecimento vale para todas as UFs.
- Commit único (`feat`): o vermelho→verde foi feito por módulo na sessão, sem commit separado do teste vermelho.

## Como verificar
```bash
cd apps/web && pnpm typecheck && pnpm lint && pnpm test          # 27 arquivos, 238 testes
pnpm test:e2e                                                     # mocks do contrato (49 + skips da API real)
# API real (nova) + e2e dos 4 candidatos e da busca:
ELEICOES_DIR_DADOS=<dados>/data/processed uv run uvicorn api.main:app_producao --factory --port 8001 &
E2E_API_REAL=1 API_ALVO=http://localhost:8001 pnpm test:e2e tests/e2e/api-real.spec.ts
```
