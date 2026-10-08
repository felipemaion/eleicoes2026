# Handoff backend — T-B08 (gastos na ficha, links oficiais, procedência)

Branch `feat/backend-proveniencia` (a partir de `origin/main` pós T-B07). `make lint test` verde; 170 testes API, cobertura 97%.

## O que mudou (contrato, aditivo — OpenAPI regenerado)
- **Ficha** `/api/candidatos/{ano}/{sq}`:
  - `gastos` agora é `GastosCandidato` (herda os campos antigos): + `repasses_contratados/pagos`, `despesa_total_contratada/paga`, `custo_voto_contratado_com_repasses`, `custo_voto_pago_com_repasses`, `receita_total`, `receita_por_fonte`, `explicacao_repasses` (texto pronto para o front). Custo "principal" segue **sem** repasses (spec §4.2); a diferença é exatamente o repasse. 2022 sai deflacionado, repasses incluídos.
  - `links: list[Link]` — `{tipo, rotulo, url, verificado, nota}`. Tipos: `votos_oficiais`, `divulgacand_lista`, `divulgacand_candidato`, `divulgacand_ficha_json`, `dados_abertos_votos`, `dados_abertos_contas`.
  - `fontes: list[Fonte]`.
- **`fontes`** (`{dataset, arquivo_oficial_url, dt_geracao, coluna_regra, metodologia_url}`) também em `/candidatos`, `/mapa`, `/gastos`, `/comparativo`. Nome do campo é `fontes` (lista), não `fonte`: cada resposta usa mais de um dataset. `/mapa` H3 aponta `votacao_secao` (com `{UF}` no URL quando sem UF).
- Catálogo único: `apps/api/src/api/fontes.py` (URLs CDN/BCB + âncora da spec em `docs/metodologia/indicadores.md` no GitHub). Links: `apps/api/src/api/links.py`. Repasses calculados em `servicos/contas.py` (`_repasses`, mesmos rótulos que a lib exclui).

## Verificação dos links (navegador, 2026-10-08)
Verificados (funcionam):
- Resultados 2026 (Dep. Federal SP, 6257): `https://resultados.tse.jus.br/oficial/app/index.html#/eleicao/6257/uf/sp/cargo/6/vis/nominal/resultados` → mostra Kim Kataguiri (MISSÃO 1414) e demais. Presidente: `.../eleicao/6257/uf/br/cargo/1/...`; senador 6257 também carregou. O app **não tem URL por candidato**.
- DivulgaCand: ids de eleição pela API oficial `/divulga/rest/v1/eleicao/ordinarias` → 2026 = `20322002026`, 2022 = `2040602022`. Lista BR: `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/BR/20322002026`.
- Ficha JSON oficial (abre no navegador): `.../divulga/rest/v1/candidatura/buscar/2022/BR/2040602022/candidato/280001607829` (Lula 2022, 200). Renan Santos 2026 = sq `280002540694`, existe na listagem oficial.
- ZIPs do CDN (HEAD 200): prestação de contas 2026 e votação 2022.

**Não consegui garantir** (marcados `verificado=false` com nota no próprio link):
- Deep link do candidato `#/candidato/{ano}/{eleicao}/{UF}/{sq}` (perfil/bens/contas): a SPA do TSE devolveu "erro ao carregar" para qualquer rota de candidato (inclusive padrões inválidos redirecionam para `#/504`), então não consegui provar nem refutar. Sugiro o Felipe abrir 1 link no navegador e me dizer se carrega; se não, trocar o padrão em `links.py` (um ponto só).
- Lista por UF (`#/candidato/SP/SP/<eleicao>`): padrão inferido do BR.
- Resultados de **2022**: o app de resultados só atende a eleição corrente (ignora `e=544`/`546`); link cai na página de estatísticas do TSE, com nota. Não achei padrão estável por candidato de 2022.
- `cd_eleicao` 2026 para governador/dep. estadual (6259) vem do ETL/docs; não carregou na mesma sessão (o app restaura a última rota).

## Pendências / decisões para o orquestrador
- Front: renderizar `links` respeitando `verificado/nota` e `fontes` (tooltip "de onde vem"). Tipos do web saem do OpenAPI.
- `dt_geracao` das `fontes` é o do manifesto global (um valor), não por arquivo.
- Commit único `feat` (não foi possível commitar o teste vermelho antes: contrato novo foi escrito junto).

## Como verificar
`uv run pytest apps/api/tests -p no:warnings` · `make lint` · `curl -s localhost:8000/api/candidatos/2026/<sq> | jq '.gastos,.links,.fontes'`
