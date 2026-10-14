# Handoff backend — T-B20 (referências + item 5, contas sem filtro de turno)

Branch `feat/backend-referencias`. Dois commits lógicos: (1) `fix(api)` contas sem `nr_turno = 1`;
(2) `GET /api/referencias`.

## O que foi feito
- **Item 5:** removido `nr_turno = 1` das views `receitas`, `despesas` e `_prestacao_da_base`
  (`repositorio/duckdb.py`). Votos/candidatos/eleitorado seguem no turno 1. Teste: sq 14 só com
  contas em `nr_turno=2` (fixture `fixtures_referencias`) → ficha com `gastos` não nulo.
- **`config/grupos.yaml`:** `presidenciaveis_2026` (critério novo `sqs:` inline), `top5_eleitos_outros_2026`
  (critério declarativo `ranking: {cargos, resultado: eleito, n, por: uf, excluir_partido}`),
  `rotulo_curto` no Missão, `rotulo_lado` por grupo e bloco `referencias: {nossos, contra}`.
  Sem código por grupo (ADR 0005); o ranking vale para qualquer ano.
- **`GET /api/referencias?cargo=&uf=&sq=`:** `nossos` × `referencia`, cada candidato com foto, partido,
  resultado e `indicadores` (votos, %válidos, penetração, nº de municípios, HHI, N efetivo, custo por
  voto pago, receita total, % público, % pessoa física) — todos via `packages/indicadores`/`contas_de`.
  `mediana` + `n_mediana` por campo no lado, `indices` (valor ÷ mediana da referência) nos nossos,
  `motivos` por indicador nulo, `motivo_vazio` (ex.: UF sem eleito de outro partido), `destacado`.
  Rótulos prontos (`rotulo`, `nossos.rotulo`, `referencia.rotulo`).
- Grupos de referência saem de `/api/grupos` e `/api/meta` (não são filtro); `/candidatos?grupo=` com
  ranking → 422 `grupo_por_ranking`.
- Varredura (`/api/referencias` × cargos × UFs) e smoke (presidente; DF SP = 5 eleitos, sem o 14).
- OpenAPI regenerado.

## Decisões
- Empate de votos → menor `sq_candidato`. Eleito = `ELEITO`, `ELEITO POR QP`, `ELEITO POR MÉDIA`.
- Presidente é nacional: `uf` é aceita e ignorada (resposta `uf: null`). Deputados sem `uf` → 422
  `uf_obrigatoria`; cargo sem grupo de referência → 422 `cargo_sem_referencia`; `sq` que não é nosso → 422.
- Finanças ausentes: nulas com motivo, nunca zero. Sem T-D10 publicada, a referência vem sem custo/receita.
- **Pendência com `analise` (T-A11):** a mediana e o índice relativo são aritmética local mínima
  (`_mediana`/`_indice` em `servicos/referencias.py`, marcados TODO). Trocar pelas funções da spec
  quando a T-A11 as publicar, mantendo os vetores. Também falta o texto público "quem × quem" (`textos.json`).
- Fixtures: novo mundo `tests/fixtures_referencias/` (gerado por `gerar_fixture.py`, que agora também o
  gera e preserva `fixtures/fotos/`), para não alterar os totais dos testes antigos.

## Para o frontend (T-W26)
Contrato novo em `docs/api/openapi.json` (`Referencias`, `Lado`, `CandidatoComparado`, `Perfil`).
`Perfil` traz todos os números como `number | null`.

## Como verificar
`make lint test`; `uv run pytest apps/api/tests/test_b20_referencias.py`;
em produção: `apps/api/scripts/smoke.py --base https://…` e `varredura.py`.
Depois do deploy: `curl '/api/referencias?cargo=DEPUTADO%20FEDERAL&uf=SP'` e conferir Lula
(`/api/candidatos/2026/280002542548` → `gastos` não nulo; precisa dos dados da T-D10 publicados).
