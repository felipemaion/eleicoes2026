# Handoff backend — T-B13 (foto_url e página do candidato no TSE)

Branch `feat/backend-foto-link` (base `origin/main` pós T-B12/#65). Sem push.

## O que mudou
- `foto_url` (`/fotos/<ano>/<sq>.webp` se `<dados>/fotos/manifesto.json` — T-D07 — tem `"<ano>/<sq>"`; senão `null`)
  e `link_tse_candidato` (`Link`, `verificado=true`) em: `/candidatos` (itens), ficha `/candidatos/{ano}/{sq}`
  (campo `candidato`), `/gastos` (`por_candidato`), `/busca` e `/evolucao/pessoas` (`de`/`para`).
  Campos vêm do mixin `api.fotos.ComFotoELink` (DRY). Manifesto lido uma vez na abertura do
  `DuckDBRepositorio`; novo `Repositorio.fotos()` (memória aceita `fotos=`). Sem manifesto → tudo `null`.
- `links.link_tse_candidato()`; o link `divulgacand_candidato` da ficha usa a mesma função.

## Padrão de URL verificado (navegador, 2026-10-08)
Rota lida no bundle do app do TSE: `#/candidato/:regiao/:uf/:eleicaoID/:candidatoID/:ano/:sgUe`.
URL: `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/<UF>/<UF>/<eleição>/<sq>/<ano>/<UF>`
(`BR` nos três segmentos de UF para presidente; eleição 20322002026 em 2026, 2040602022 em 2022).
Abertos e conferidos pelo nome na página: Renan Santos 2026 (BR), Kim 2026 e 2022 (SP), Rafa Minato 2026
e Guto Zacarias 2022 (dep. estaduais SP). O padrão anterior (`/candidato/<ano>/<eleição>/<uf>/<sq>`)
**não existe** (“Erro ao carregar a página”) — foi substituído; testes do b08 atualizados.
Obs.: a SPA às vezes não carrega com o overlay de lista (cargo vazio) — afeta só a lista, não o perfil.

## Decisões
- Foto ausente = `null` (front mostra avatar neutro); manifesto ausente não é erro (fotos opcionais).
- `link_tse_candidato` repete o objeto `Link` em cada item (~250 B); aceitável com os limites de página.

## Verificar
`.venv/bin/pytest apps/api` (213 passam; cobertura api 98%), `make openapi` (regenerado e commitado),
`ruff` e `mypy --strict` limpos. Teste novo: `apps/api/tests/test_b13_foto_link.py` + fixture
`tests/fixtures/fotos/manifesto.json`. Manifesto real (dados worktree): 48.996 fotos lidas em 0,04 s.

## Pendências
- Frontend: tipos do OpenAPI mudaram (campos novos obrigatórios nos itens).
- Orquestrador/Oracle: servir `public/fotos/` em `/fotos/*` (ver handoff dados-T-D07) e ter `data/processed/fotos/manifesto.json`
  no diretório de dados da API em produção, senão `foto_url` sai `null`.
