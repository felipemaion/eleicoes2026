# 0004 — CPF/título viram `pessoa_id` (hash salgado)

- **Status:** aceito · 2026-10-07
- **Contexto:** `SQ_CANDIDATO` muda a cada eleição; ligar a mesma pessoa em 2022 e 2026 exige CPF ou
  título, dados pessoais que não devem ser republicados num repositório público.
- **Decisão:** o ETL calcula `pessoa_id = sha256(sal || cpf_normalizado)`; o sal fica fora do repo
  (`.env` local). CPF/título nunca chegam a Parquet, log, fixture ou API.
- **Consequências:** ligação 2022↔2026 possível sem expor PII.
