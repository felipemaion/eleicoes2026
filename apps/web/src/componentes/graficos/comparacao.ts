import { axisBottom, extent, scaleBand, scaleLinear, select } from "d3";
import { formatarDecimal } from "../../formato";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico } from "./base";

export interface ParAntesDepois {
  rotulo: string;
  antes: number;
  depois: number;
}

export interface OpcoesComparacao {
  titulo: string;
  rotuloAntes: string;
  rotuloDepois: string;
  formato?: (v: number) => string;
  largura?: number;
}

const ESQ = 150;
const DIR = 24;
const TOPO = 8;
const BAIXO = 28;
const LINHA = 28;

/** Dumbbell: cada linha liga o valor antes ao depois, sobre o MESMO eixo. */
function desenhar(container: HTMLElement, dados: readonly ParAntesDepois[], o: OpcoesComparacao): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const fmt = o.formato ?? formatarDecimal;
  const w = o.largura ?? 640;
  const h = TOPO + BAIXO + dados.length * LINHA;
  const [min = 0, max = 1] = extent(dados.flatMap((d) => [d.antes, d.depois]));
  const x = scaleLinear().domain([Math.min(0, min), max === min ? min + 1 : max]).nice().range([ESQ, w - DIR]);
  const y = scaleBand<number>().domain(dados.map((_, i) => i)).range([TOPO, h - BAIXO]).padding(0.3);

  const svg = criarSvg(w, h, `${o.titulo}. Comparação de ${o.rotuloAntes} para ${o.rotuloDepois} em ${String(dados.length)} itens; ${String(dados.filter((d) => d.depois > d.antes).length)} subiram.`);
  const eixo = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  eixo.call(axisBottom(x).ticks(5).tickFormat((v) => fmt(+v)));
  eixo.selectAll("text").attr("fill", "var(--cor-texto-suave)");
  eixo.selectAll("path,line").attr("stroke", "var(--cor-borda)");

  dados.forEach((d, i) => {
    const cy = (y(i) ?? 0) + y.bandwidth() / 2;
    svg.append(
      textoSvg(ESQ - 6, cy + 4, d.rotulo, { class: "rotulo", "text-anchor": "end" }),
      no("line", { class: d.depois >= d.antes ? "ligacao alta" : "ligacao baixa", x1: x(d.antes), x2: x(d.depois), y1: cy, y2: cy, stroke: "var(--cor-texto-suave)", "stroke-width": 2 }),
    );
    for (const [valor, rotulo, cor] of [[d.antes, o.rotuloAntes, COR.antes], [d.depois, o.rotuloDepois, COR.depois]] as const) {
      const c = no("circle", { class: "marca", cx: x(valor), cy, r: 6, fill: cor });
      marcaAcessivel(c, `${d.rotulo}, ${rotulo}: ${fmt(valor)}`);
      svg.append(c);
    }
  });

  const legenda = document.createElement("ul");
  legenda.className = "legenda-grafico";
  for (const [rotulo, cor] of [[o.rotuloAntes, COR.antes], [o.rotuloDepois, COR.depois]] as const) {
    const li = document.createElement("li");
    li.className = "legenda-item";
    const amostra = document.createElement("span");
    amostra.className = "amostra";
    amostra.style.background = cor;
    li.append(amostra, rotulo);
    legenda.append(li);
  }

  container.replaceChildren(
    svg,
    legenda,
    tabelaAlternativa(o.titulo, ["Item", o.rotuloAntes, o.rotuloDepois, "Variação"], dados.map((d) => [d.rotulo, fmt(d.antes), fmt(d.depois), fmt(d.depois - d.antes)])),
  );
}

export function render(container: HTMLElement, dados: readonly ParAntesDepois[], opcoes: OpcoesComparacao): Grafico<readonly ParAntesDepois[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
