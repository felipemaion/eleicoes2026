/**
 * Barras divergentes em torno de 1× (= igual à mediana da referência). Escala logarítmica: 0,5× e 2×
 * ficam à mesma distância de 1×. Direção dita por posição, classe e texto (nunca só por cor), e sem
 * juízo de valor: custo por voto abaixo da mediana não é "pior" nem "melhor" por si.
 */
import { axisBottom, scaleBand, scaleLog, select } from "d3";
import { corpoRico, criarFlutuante, ligarMarca } from "../ui/tooltip";
import { FORMATO_INDICE } from "../../dados/referencias-logica";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, substituir, tabelaAlternativa, textoSvg, type Grafico } from "./base";
import { larguraEstimada, quebrarLinhas } from "./barras";
import { PALETAS } from "../../paletas";

export interface PontoIndice { chave: string; rotulo: string; valor: number }
export interface OpcoesIndice { titulo: string; nome: string; largura?: number }

const COR_ACIMA = PALETAS.categorica[5];
const COR_ABAIXO = PALETAS.categorica[6];
const TOPO = 22;
const BAIXO = 30;
const LINHA = 30;
const DIR = 56;
const MIN_ESCALA = 0.1;
const MAX_ESCALA = 10;

let balao: ReturnType<typeof criarFlutuante> | null = null;
function tooltip(): ReturnType<typeof criarFlutuante> {
  if (!balao?.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

const posicao = (v: number): "acima" | "abaixo" | "igual" => (v > 1 ? "acima" : v < 1 ? "abaixo" : "igual");
const DESCRICAO = { acima: "acima da mediana", abaixo: "abaixo da mediana", igual: "igual à mediana" } as const;

export function desenhar(container: HTMLElement, dados: readonly PontoIndice[], o: OpcoesIndice): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const w = o.largura ?? 640;
  const maior = Math.max(...dados.map((d) => larguraEstimada(d.rotulo)));
  const ESQ = Math.round(Math.min(Math.max(140, maior + 12), w * 0.4));
  const maxChars = Math.max(10, Math.floor((ESQ - 12) / (maior / Math.max(...dados.map((d) => d.rotulo.length)))));
  const h = TOPO + BAIXO + dados.length * LINHA;
  // Recorta em [0,1×; 10×]: valores além disso encostam na borda (o texto da barra diz o valor real).
  const lim = (v: number): number => Math.min(Math.max(v, MIN_ESCALA), MAX_ESCALA);
  const x = scaleLog().domain([MIN_ESCALA, MAX_ESCALA]).range([ESQ, w - DIR]);
  const y = scaleBand<number>().domain(dados.map((_, i) => i)).range([TOPO, h - BAIXO]).padding(0.25);
  const x1 = x(1);

  const svg = criarSvg(w, h, `${o.titulo}. ${String(dados.length)} indicadores de ${o.nome} em vezes a mediana da referência; 1× é igual à mediana.`);
  const eixo = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  eixo.call(axisBottom(x).tickValues([0.1, 0.25, 0.5, 1, 2, 4, 10]).tickFormat((v) => FORMATO_INDICE(+v)));
  eixo.selectAll("text").attr("fill", "var(--cor-texto-suave)");
  eixo.selectAll("path,line").attr("stroke", "var(--cor-borda)");
  svg.append(textoSvg(x1 - 6, 12, "← abaixo da mediana", { "text-anchor": "end", "font-size": 11, fill: "var(--cor-texto-suave)" }));
  svg.append(textoSvg(x1 + 6, 12, "acima da mediana →", { "text-anchor": "start", "font-size": 11, fill: "var(--cor-texto-suave)" }));

  dados.forEach((d, i) => {
    const yi = y(i) ?? 0;
    const xv = x(lim(d.valor));
    const pos = posicao(d.valor);
    const cor = pos === "acima" ? COR_ACIMA : pos === "abaixo" ? COR_ABAIXO : COR.zero;
    const linhas = quebrarLinhas(d.rotulo, maxChars);
    const rotulo = textoSvg(ESQ - 6, yi + y.bandwidth() / 2 + 4 - ((linhas.length - 1) * 7), "", { class: "rotulo", "text-anchor": "end" });
    linhas.forEach((l, k) => { rotulo.append(no("tspan", { x: ESQ - 6, dy: k === 0 ? 0 : 14 }, l)); });
    const r = no("rect", { class: `marca ${pos}`, x: Math.min(x1, xv), y: yi, width: Math.max(Math.abs(xv - x1), pos === "igual" ? 2 : 0), height: y.bandwidth(), fill: cor });
    marcaAcessivel(r, `${d.rotulo}: ${FORMATO_INDICE(d.valor)} a mediana, ${DESCRICAO[pos]}`);
    r.dataset["tooltip"] = `${d.rotulo} · ${FORMATO_INDICE(d.valor)}`;
    ligarMarca(r, tooltip(), () => corpoRico({
      titulo: d.rotulo,
      linhas: [[o.nome, `${FORMATO_INDICE(d.valor)} a mediana`], ["Leitura", DESCRICAO[pos]]],
    }));
    // Barra que vai até a borda esquerda não deixa espaço para o valor: ele passa para o lado direito da linha.
    const naDireita = xv >= x1 || xv - ESQ < 36;
    const ancora = xv >= x1 ? xv : x1;
    const texto = textoSvg(naDireita ? ancora + 4 : xv - 4, yi + y.bandwidth() / 2 + 4, FORMATO_INDICE(d.valor), { class: "valor", "font-size": 11, "text-anchor": naDireita ? "start" : "end" });
    svg.append(rotulo, r, texto);
  });
  svg.append(no("line", { class: "referencia", x1, x2: x1, y1: TOPO - 4, y2: h - BAIXO, stroke: "var(--cor-texto)", "stroke-width": 1.5 }));

  substituir(container, svg, tabelaAlternativa(o.titulo, ["Indicador", `${o.nome} ÷ mediana`, "Leitura"], dados.map((d) => [d.rotulo, FORMATO_INDICE(d.valor), DESCRICAO[posicao(d.valor)]])));
}

export function render(container: HTMLElement, dados: readonly PontoIndice[], opcoes: OpcoesIndice): Grafico<readonly PontoIndice[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
