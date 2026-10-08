# Como ler este painel

Este painel mostra como foram, nas eleições gerais de 2026, os candidatos do **Partido Missão
(número 14)**: quantos votos tiveram, onde, quanto gastaram e como isso se compara ao grupo de
candidatos ligados ao MBL em 2022, que concorreram por outros partidos. Todos os números vêm de
fontes oficiais: **Tribunal Superior Eleitoral (TSE)**, **IBGE** e **Banco Central**.

## A medida principal: penetração

Comparar votos brutos engana: uma cidade grande sempre dá mais votos que uma pequena. Por isso a
medida principal do painel é a **penetração**: quantos votos o candidato teve **para cada mil
eleitores aptos** daquele lugar (‰).

- 12 ‰ quer dizer 12 votos a cada mil eleitores que podiam votar ali.
- Como a conta usa o eleitorado, e não quem compareceu, ela não muda com a abstenção nem com o
  número de concorrentes. É a única taxa que dá para comparar entre 2022 e 2026.

O **% dos votos válidos** também aparece: é a fatia do candidato entre os votos dados a
candidatos e partidos (sem brancos e nulos). Serve bem para comparar candidatos da mesma eleição,
mas varia com o comparecimento.

## Como ler o mapa

- **Cores** mostram sempre **taxas** (penetração, % dos válidos, quociente locacional). Nunca
  pintamos municípios por número de votos, porque isso só repetiria o mapa da população.
- **Quantidades** (votos) aparecem como **círculos** (a área é proporcional aos votos) ou como
  **hexágonos** de densidade.
- **Áreas hachuradas** são **estimativas instáveis**: ali se esperariam menos de 20 votos para o
  candidato, e poucos votos a mais ou a menos mudam muito a taxa. Olhe, mas não conclua.
- **Cinza claro** é "sem dado".
- 2022 e 2026 usam **as mesmas faixas de cor**, para que a mesma cor signifique o mesmo valor
  nos dois mapas.
- A opção **suavizada** aproxima as taxas instáveis de municípios pequenos da média do estado; é
  uma estimativa, e o número oficial fica sempre no detalhe.
- O **quociente locacional (LQ)** compara a força do candidato num município com a força dele no
  estado: 1 é igual à média, 2 é o dobro. Municípios com LQ de 2 ou mais (e votos suficientes)
  são chamados de **redutos**.

## Votos de legenda não são de candidatos

Na eleição para deputado o eleitor pode votar só no número do partido: o **voto de legenda**.
Esses votos contam para o partido e para a divisão de cadeiras, mas **não são atribuídos a
nenhum candidato**. Eles aparecem só na **votação do partido** (votos nominais dos candidatos +
legenda).

## Comparar 2022 com 2026

- **Zonas eleitorais não são comparadas entre anos.** Houve **rezoneamento**: a Justiça Eleitoral
  criou, extinguiu e redesenhou zonas, e a mesma zona, pelo número, pode cobrir outra área. As
  comparações usam **municípios** (municípios criados depois de 2022 são somados aos de origem) e
  **hexágonos** de tamanho fixo.
- A medida principal da evolução é a **variação da penetração**, em pontos por mil eleitores.
  Também mostramos a variação dos válidos em **pontos percentuais (p.p.)**, a retenção (votos de
  2026 ÷ votos de 2022) e o ganho em votos.
- Só o **1º turno** é comparado, sempre **no mesmo cargo**. O **Senado** fica de fora: em 2022
  cada eleitor votou em um senador; em 2026, em dois.
- Grupos de tamanhos diferentes são comparados também **por candidato** e no recorte **"mesmos
  candidatos"** (só quem disputou as duas eleições). O número de candidaturas aparece sempre.

### O comparador

A tela de evolução é um **comparador**: de um lado fica **2022**, do outro **2026**. Em cada lado
você escolhe, em **"Alterar"**, um **grupo pronto** (abaixo) ou **candidatos** achados pela
busca (nome, número ou partido).

- Só se compara o **mesmo cargo na mesma UF** (escolhidos na barra de filtros). Uma candidatura
  que não concorreu a esse cargo nessa UF não entra, e o cartão do lado avisa.
- A comparação é **por município e hexágono**, nunca por zona eleitoral (ver acima).
- Se um lado tem muito mais candidaturas que o outro, olhe também os números **por candidato**.

### Indicados e grupos

- **Indicados**: as **4 candidaturas de 2022 que o MBL indicou** para concorrer por outro
  partido, todas pelo União Brasil: **Kim Kataguiri, Guto Zacarias, Renato Battista e Cristiano
  Beraldo**. Na tela, aparecem com o selo "indicado pelo MBL".
- **Grupo MBL 2022**: **18 candidaturas** de 2022, os **4 indicados** e mais **14** pessoas que
  concorreram pelo Missão em 2026 e também disputaram 2022, por qualquer partido. Vários destes
  14 **não eram do MBL em 2022**; o critério foi definido pelo autor do painel. O recorte
  **"indicados"** mostra só os 4 primeiros.
- **Grupo MBL 2026**: todas as candidaturas do **Partido Missão** em 2026 **mais Cristiano
  Beraldo**, que em 2026 concorreu pelo **PP**.
- **Partido Missão 2026**: só as candidaturas do Missão (número 14).

A lista de referência é pública no repositório (`data/reference/mbl_2022.csv`).

### O número 14 em 2022 era do PTB

Em 2022 o número 14 pertencia ao **PTB** (Partido Trabalhista Brasileiro), sem relação com o
Missão; o PTB foi extinto em 2023, ao se fundir com o Patriota no PRD. **Votos no 14 em 2022 não
são votos do Missão.** O painel compara pessoas e grupos, nunca o número do partido.

## Dinheiro de campanha

- As **receitas** são separadas por fonte: **Fundo Eleitoral (FEFC)** e **Fundo Partidário**
  (dinheiro público), **pessoas físicas**, **recursos próprios** do candidato, **financiamento
  coletivo** e outras.
- **Custo por voto** = despesa da campanha ÷ votos nominais. Há a versão **contratada** (tudo o
  que foi contratado) e a **paga** (o que já saiu do caixa). Repasses a outros candidatos não
  contam como despesa.
- **As contas de 2026 são parciais** até a prestação de contas final: valores podem ser lançados
  ou corrigidos. Cada tela informa a data em que o TSE gerou os dados.
- **Inflação:** valores de 2022 são corrigidos pelo **IPCA** (Banco Central, série 433) até o
  mês-base informado na tela (setembro de 2026 assim que o índice for publicado). Valores de 2026
  aparecem como declarados.

## Perfil espacial do voto

Na página de cada candidato, a votação é classificada em quatro perfis (tipologia de **Ames**),
cruzando duas medidas:

- **Concentração** (índice G): a votação segue a distribuição do eleitorado ou se concentra em
  poucos lugares?
- **Dominância**: onde o candidato tem votos, ele lidera a disputa local ou divide com muitos?

| | Dominante | Compartilhado |
|---|---|---|
| **Concentrado** | reduto clássico | poucas áreas, disputadas |
| **Disperso** | forte em muitos lugares | voto de opinião |

O corte é a mediana dos candidatos competitivos (com ao menos 10 % do quociente eleitoral) do
mesmo cargo e estado, de **todos os partidos**. É uma comparação relativa àquela disputa.

## Redes sociais

A aba **Redes sociais** mostra o Instagram dos candidatos do Partido Missão. Os perfis são os que
cada candidato **declarou ao TSE** no registro de candidatura; os números vêm da **API oficial da
Meta**, coletados uma vez por dia a partir de 8 de outubro de 2026.

- **Três períodos:** **pré-campanha** (1/1 a 15/8/2026), **campanha** (16/8, quando a propaganda
  passa a ser permitida, até o 1º turno, em 4/10) e **pós-eleição** (de 5/10 em diante). Como têm
  tamanhos muito diferentes, comparamos posts e vídeos **por semana**, e não o total.
- **Engajamento** = curtidas + comentários de um post, em % dos seguidores. Mostramos a
  **mediana** (o post típico). Posts com **curtidas ocultas** ficam fora da conta — não valem
  zero.
- **Votos por mil seguidores** compara o tamanho da rede com o resultado nas urnas.
- **Voto acima ou abaixo do esperado:** traçamos a tendência entre seguidores e votos dos
  candidatos do mesmo cargo; um valor 2 quer dizer o dobro dos votos esperados para aquele
  número de seguidores.
- **Seguidores só daqui para a frente:** o Instagram não informa quantos seguidores uma conta
  tinha no passado. Antes e depois da eleição, só dá para comparar os posts, que têm data.
- **Contas pessoais** não permitem consulta pela API: aparecem só com o link e ficam fora das
  médias. A tela diz quantas são.

**Andar junto não é causa.** Se candidatos com mais seguidores tiveram mais votos, isso não
prova que a rede trouxe os votos: quem já é conhecido atrai as duas coisas. E seguidores não são
eleitores — incluem pessoas de outros estados, menores de idade e perfis falsos.

## Resultados podem mudar

Candidaturas **sub judice** (registro em julgamento) podem ter votos validados, anulados ou
convertidos em legenda depois da eleição. O painel reflete os dados do TSE na data indicada em
cada tela.

## Para saber mais

- Definições, fórmulas e referências de cada indicador: [`indicadores.md`](../indicadores.md).
- Cuidados metodológicos: [`cuidados.md`](../cuidados.md).
- Textos curtos usados nas telas: [`textos.json`](textos.json).
