# Handoff frontend — T-W26 (aba Comparar com outros partidos)

Branch `feat/frontend-referencias` (sobre `origin/main` com T-B20 e T-A11).

## O que foi feito
- Aba `#/comparar` ("Comparar partidos"): seletor de 3 blocos (Presidente, Dep. federal, Dep. estadual), UF para deputados
  (padrão: filtro global; "Brasil" vira SP), frase da API como título do bloco + texto "quem × quem" de `textos.json`,
  legenda fixa dos dois lados (■ Missão em verde, ◆ referência em rosa; forma + cor).
- Tabela lado a lado: 5 de referência + mediana + nosso; "?" por indicador (textos.json); linhas de contexto (votos, receita) marcadas.
  Dado ausente = "sem dado" (nunca zero), com motivo da API em balão (componente T-W23, testado dentro da viewport).
- Nosso candidato: padrão o mais votado do Missão (ou o `destacado`), troca por busca (máx. 8 resultados). Fotos/nomes levam à ficha.
- Gráfico novo `graficos/indice-mediana.ts`: barras divergentes em 1×, escala log (0,1×–10×), direção por posição+texto+classe,
  tabela alternativa, sem juízo de valor.
- Mobile 390 px: tabela vira cartões por indicador; sem rolagem horizontal.
- Acréscimo (T-B21 c): linhas "Receita por voto" e "Despesa ÷ receita" + selo "possível declaração incompleta" (`alerta_declaracao`);
  R$/voto nas duas bases (custo por voto = despesa paga; receita por voto). **Preparado, não contratado**: o OpenAPI ainda não tem
  esses campos; tipos locais opcionais em `referencias-logica.ts`, e as linhas só aparecem quando a API enviar (fixture já traz).

## Decisões
- Estado (bloco, UF, nosso) é local da tela, não vai ao hash nem ao store global; só a tela entrou em `TELAS`.
- `textos.ts`: tela `comparar` usa a seção `referencias`; avisos `referencias_presidenciaveis` (só presidente) e
  `referencias_topo_dos_eleitos` (só deputados) filtrados por contexto.
- Índices vêm da API (`indices`); o front não recalcula.

## Pendências
- Quando T-B21 sair: `pnpm gen:api`, trocar os tipos locais por `S["Perfil"]` e confirmar nome/unidade de `despesa_sobre_receita`
  (hoje formatado com 2 casas, "0,85") e onde vem `alerta_declaracao` (suposto no candidato).
- Stash `w26` guarda PNGs de handoffs antigos (T-W16/T-W23) que estavam sujos no worktree; não são desta tarefa.

## Como verificar
`cd apps/web && pnpm typecheck && pnpm lint && pnpm test && pnpm test:e2e` (391 unit, 92 e2e verdes).
Capturas: `docs/registro/handoffs/img/T-W26-comparar-{desktop,presidente,mobile}.png`.
