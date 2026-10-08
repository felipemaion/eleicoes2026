# Handoff backend — T-B12 (relevância da busca)

- **Feito:** `/api/busca` e `/api/evolucao/pessoas?q=` ordenam por nível: 0 urna exata, 1 começo do nome (urna/civil), 2 começo de palavra (inclui sigla), 3 trecho; empate por votos (maior primeiro), sem acento/caixa. Termo numérico: número exato, prefixo, partido.
- **Onde:** `texto.nivel_relevancia` + `Candidatura.nivel` (Python); `_casamento` em `repositorio/duckdb.py` (mesmo nível em SQL); desempate por votos em `servicos/busca.py`.
- **Decisão/limite:** votos não estão na tabela de candidatos; o SQL ordena por nível e devolve uma janela de 500 (`JANELA_RELEVANCIA`), o serviço reordena por nível+votos e corta em `limite`. Se um único nível tiver >500 casos, o desempate por votos vale só dentro da janela.
- **Contrato:** OpenAPI inalterado (`make openapi` sem diff).
- **Verificar:** `uv run pytest apps/api/tests -q` (98% cobertura, inclui `test_b12_relevancia.py` com kim/renan/guto/14 e varredura da fixture); ruff e mypy verdes. Varredura em produção (`apps/api/scripts/varredura.py --base ...`) não rodada daqui — fica para pós-deploy: conferir `q=kim` com KIM KATAGUIRI antes de ELIKA TAKIMOTO.
