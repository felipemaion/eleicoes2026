# Handoff dados — T-D05 (votação por seção → local → H3)
Branch `feat/dados-secao-h3` (test → feat → feat cli → docs). Pacotes etl+contratos: testes, ruff e mypy do código novo verdes (secao.py 95% de cobertura; total etl+contratos 93%).

## Entregue (execução real, Brasil inteiro, local)
- `etl secao --ano 2022|2026 --baixar --descartar-zip` → `data/processed/{votos_local,totais_local}/ano=<ano>/<UF|BR>.parquet` e `locais_h3/ano=<ano>/locais_h3.parquet`. Contratos em `contratos/tse.py`.
- **Tempo**: 2022 = 143 s; 2026 = 121 s (download + blocos de 256 MB; ZIP apagado após validar). **Tamanho**: 61 MB + 5 MB + 5 MB ≈ **71 MB** somados os dois anos (meta < 300 MB; sem precisar restringir candidatos).
- Linhas lidas: 2022 = 72.978.729 (2.841.231 de 2º turno ignoradas); 2026 = 67.858.746. Votos nominais: 2022 = 538.116.046; 2026 = 655.892.177 (2026 é parcial, `dt_geracao` 06/10).
- Totais de controle (todos passaram, por UF, antes de publicar): linhas do fluxo = linhas lidas; Σ texto = nominais+legenda+brancos+nulos; Σ votos_local = totais_local; **todo candidato do munzona bate exatamente** com a soma dos locais.
- **Divergência explicada**: o arquivo por seção traz candidaturas ausentes do munzona (votos anulados/candidaturas indeferidas). Ficam em `votos_local`. 2022 = 695 candidaturas / 2.741.284 votos; 2026 = 241 / 335.602.
- `locais_h3`: 2022 = 85.626 de 92.386 locais com H3 (6.760 sem coordenada); 2026 = 94.343 de 95.570 (1.227 sem).

## Alerta de coordenada (> 5%)
- **2022: 5,83% dos votos nominais em locais sem coordenada** (acima do limite). Por UF: **BA 29,5%, ES 29,8%, SE 26,5%**, AP 11,4%, MG 8,7%, RR 8,5%, PA 8,1%, MS 6,0%, ZZ 100% (exterior, esperado). Esses estados terão mapa H3 de 2022 fraco: é limite da fonte, não do ETL.
- 2026: 1,13% (AP 11,6%, RR 6,5%, ZZ 100%): ok.
- Além disso há locais com voto que **não existem** no `eleitorado_local_votacao` do 1º turno (renumeração de local): 2022 = 5,3 M votos (PA 775 mil, MS 418 mil, MT, BA, SP), 2026 = 6,5 M (PA, SP, MG). Entram no total sem coordenada. Recuperar exige outra fonte de coordenada; não inventei.

## Decisões
- **Nomes seguem o backend, não o brief**: `nr_local` (não `nr_local_votacao`), `h3` = res 8, mais `h3_r7`, `h3_r6`; `ano` só pela partição hive. `locais_h3` tem `lat, lon, aptos` (= `qt_eleitor_secao`).
- **Só 1º turno** (a API não filtra turno nessas tabelas; o contrato trava `nr_turno = 1`).
- `votos_local` = votos nominais (inclui anulados sub judice; o munzona "válidos" é menor para esses). Quem precisar de válidos deve usar o munzona.
- Extra `totais_local` (nominais, legenda, brancos, nulos por local × cargo) em vez de baixar `detalhe_votacao_secao`: o arquivo por seção já tem tudo; aptos vêm do eleitorado. **`detalhe_votacao_secao` não foi baixado.**
- Catálogo: `BR` entra em `UFS` (presidente); 2022 não tem `_ZZ` (404, exterior vem no BR); 2026 `_ZZ` só tem cabeçalho (tratado como vazio).
- Disco local tinha ~6 GB livres: leitura em blocos (`tse_csv.blocos_utf8`) e `--descartar-zip`; ZIPs de `votacao_secao` não ficam em `data/raw` (sha256 no manifesto).

## Pendências
- Backend: `votos_local` traz também cargo 1 (presidente) com `sg_uf` real por linha (arquivo `BR.parquet`) e `cd_cargo`; a query de `votos_h3` filtra só `sq_candidato`, sem problema, mas confirmar. `cd_mun_ibge` é nulo para o exterior.
- `etl secao` não está no `make etl` (Makefile fora do meu território). Rodar `make etl` não regenera H3; sugerir incluir.
- 2026 muda diariamente: reprocessar `votacao_candidato_munzona` 2026 junto, senão o controle por candidato pode divergir.

## Verificar
`uv run pytest packages/etl packages/contratos -q`; `uv run etl secao --ano 2022 --uf AC` (ZIP precisa estar em `data/raw` ou usar `--baixar`).
