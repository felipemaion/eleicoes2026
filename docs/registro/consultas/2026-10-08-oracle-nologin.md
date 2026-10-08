# Pedido ao Oracle — forced-command não executa (shell nologin)
De: orquestrador Eleicoes2026 (tmux `Eleicoes2026:0`).

Ao publicar os Parquet com a chave `~/.ssh/eleicoes-rsync-datasets`:
- rsync oficial 3.5.1 (Homebrew; o openrsync do macOS também falhou): `protocol version mismatch -- is your shell clean?`
- `ssh -i ~/.ssh/eleicoes-rsync-datasets eleicoes01@167.126.3.134 true` → **"This account is currently not available."**

O sshd executa o `command="..."` do authorized_keys pelo **shell de login** do usuário; com
`/usr/sbin/nologin` nenhum forced-command roda (deploy, rsync do bundle e rsync dos datasets). O seu
SERVER.md prevê `--shell /bin/bash` para o user de deploy. Pode ajustar (`usermod -s /bin/bash eleicoes01`,
mantendo senha travada e sem pty) e confirmar as 3 chaves? Comando de teste que vou rodar depois:
`rsync -az --delete -e "ssh -i ~/.ssh/eleicoes-rsync-datasets" data/processed/ eleicoes01@167.126.3.134:`
Responda em `/private/tmp/claude-501/-Users-maion-Projects-Eleicoes2026/bef97382-927e-473d-9c0d-362ca1257a5c/scratchpad/oracle-nologin.md` e diga só "respondido".
