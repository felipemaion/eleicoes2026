# Handoff frontend — T-W14 (grupos completos no seletor)
Branch `feat/frontend-grupos` (sobre origin/main 40a2e07).

## Feito
- Seletor "Grupo comparado" lista os grupos de `/api/grupos` (inclui `mbl_2026`, `mbl_2022_indicados`); `GRUPOS` fixo removido do `store` (`Grupo = string`).
- Descrição curta montada da API (`rótulo — eleição de ANO, N candidaturas.`), pois a API não tem campo `descricao`.
- Hash: `grupo=` validado só por formato (`^[a-z0-9_]{1,64}$`); grupo desconhecido da API segue visível no seletor.
- Evolução: comparação padrão = a que termina no grupo filtrado (`mbl_2026` → "MBL 2022 → MBL 2026"), senão a primeira.
- Fixture `grupos.json` com os 4 grupos. Testes: unit (lógica, componente) + 2 e2e novos.

## Pendências
- Item 2 do brief (`limite=8` na busca) aguarda a T-B12; não feito.
- Se quiserem descrição editorial por grupo, pedir `descricao` em `config/grupos.yaml` + API ao backend.

## Verificar
`cd apps/web && pnpm typecheck && pnpm lint && pnpm test && pnpm build && npx playwright test`
(atenção: `reuseExistingServer` serve o `dist` antigo se houver preview na :4173 — rode `pnpm build` antes.)
