import { axisBottom, scaleBand, scaleLinear, select } from "d3";
import { formatarNumero } from "../../formato";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico } from "./base";

export interface Barra {
  rotulo: string;
  valor: number;
}

export interface OpcoesBarras {
  titulo: string;
  formato?: (v: number) => string;
  /** Domínio fixo do eixo de valor — pequenos múltiplos usam o mesmo para serem comparáveis. */
  dominioMax?: number;
  largura?: number;
  /** Prefixa o rótulo (ex.: posição no ranking). */
  prefixo?: (b: Barra, i: number) => string;
  /** Rótulo da coluna de valor na tabela alternativa. */
  colunaValor?: string;
}

const ESQ = 150;
const DIR = 60;
const TOPO = 8;
const BAIXO = 28;
const LINHA = 26;

/** Desenha barras horizontais em `container` (substitui o conteúdo). */
export function desenhar(container: HTMLElement, dados: readonly Barra[], o: OpcoesBarras): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const fmt = o.formato ?? formatarNumero;
  const w = o.largura ?? 640;
  const h = TOPO + BAIXO + dados.length * LINHA;
  const rot = (b: Barra, i: number): string => (o.prefixo ? o.prefixo(b, i) : "") + b.rotulo;
  const x = scaleLinear().domain([0, o.dominioMax ?? Math.max(...dados.map((d) => d.valor), 0)]).nice().range([ESQ, w - DIR]);
  if (x.domain()[1] === 0) x.domain([0, 1]);
  const y = scaleBand<number>().domain(dados.map((_, i) => i)).range([TOPO, h - BAIXO]).padding(0.25);

  const svg = criarSvg(w, h, `${o.titulo}. Gráfico de barras com ${String(dados.length)} itens; maior valor: ${fmt(Math.max(...dados.map((d) => d.valor)))}.`);
  const eixo = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  eixo.call(axisBottom(x).ticks(5).tickFormat((v) => fmt(+v)));
  eixo.selectAll("text").attr("fill", "var(--cor-texto-suave)");
  eixo.selectAll("path,line").attr("stroke", "var(--cor-borda)");

  dados.forEach((d, i) => {
    const yi = y(i) ?? 0;
    const larg = Math.max(x(d.valor) - ESQ, 0);
    svg.append(textoSvg(ESQ - 6, yi + y.bandwidth() / 2 + 4, rot(d, i), { class: "rotulo", "text-anchor": "end" }));
    const r = no("rect", { class: "marca", x: ESQ, y: yi, width: larg, height: y.bandwidth(), fill: COR.principal });
    marcaAcessivel(r, `${rot(d, i)}: ${fmt(d.valor)}`);
    svg.append(r, textoSvg(ESQ + larg + 4, yi + y.bandwidth() / 2 + 4, fmt(d.valor), { class: "valor", "font-size": 11 }));
  });

  container.replaceChildren(svg, tabelaAlternativa(o.titulo, ["Item", o.colunaValor ?? "Valor"], dados.map((d, i) => [rot(d, i), fmt(d.valor)])));
}

export function render(container: HTMLElement, dados: readonly Barra[], opcoes: OpcoesBarras): Grafico<readonly Barra[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
