# Handoff frontend — T-W21 (foto some no tooltip de Gastos em produção)

**Causa real (não era a da T-W17):** o ETag da API depende só de `(DT_GERACAO, URL)` (`apps/api/src/api/cache_http.py`),
com `Cache-Control: public, max-age=300`. Quando um deploy muda o *formato* da resposta sem mudar o `DT_GERACAO`
(T-W15 acrescentou `foto_url` e `link_tse_candidato` a `/api/gastos`), o navegador de quem já abrira aquela URL
revalida, recebe 304 e segue usando o JSON antigo — sem foto e sem link. Por isso `?uf=SP` (URL visitada antes) falhava
e `mbl_2026`/Brasil (URL nunca visitada) funcionava. O ponto "do topo" não tem caminho de desenho próprio:
o código do tooltip estava certo (em produção, carga limpa, o Kim mostra foto + "Clique para abrir no TSE").

**Correção (frontend):** cada chamada à API leva `v=<sha do build>` (`src/versao.ts`, injetado no build pelo Vite;
vazio em dev/testes). URL nova ⇒ ETag novo ⇒ cache antigo não é reaproveitado depois de um deploy.
Também: removidos os `<title>` nativos do `<svg>` do gráfico e das marcas (`base.ts`); o `aria-label` permanece.

**Pendência para o backend (raiz do problema):** o ETag deveria incluir uma versão do contrato/imagem (ex.: sha
da imagem ou hash do OpenAPI), senão qualquer mudança de formato futura repete o problema para quem tem cache.

**Verificar:** `pnpm test`; `pnpm exec playwright test tests/e2e/gastos-evolucao.spec.ts -g T-W21` — o teste simula a
resposta antiga (sem foto/link) para URLs sem `v` e percorre **todos** os pontos, com `uf=SE` no grupo padrão e em
`mbl_2026`. Confirmado vermelho sem o `v` (foto ausente) e verde com ele.
