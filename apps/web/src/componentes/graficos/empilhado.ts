import { axisBottom, scaleBand, scaleLinear, select } from "d3";
import { formatarMoeda } from "../../formato";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico } from "./base";

export interface ReceitaPorFonte {
  rotulo: string;
  valores: Readonly<Record<string, number>>;
}

export interface OpcoesEmpilhado {
  titulo: string;
  largura?: number;
}

const ESQ = 150;
const DIR = 20;
const TOPO = 8;
const BAIXO = 28;
const LINHA = 28;

function desenhar(container: HTMLElement, dados: readonly ReceitaPorFonte[], o: OpcoesEmpilhado): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const fontes = [...new Set(dados.flatMap((d) => Object.keys(d.valores)))];
  if (fontes.length > COR.serie.length) throw new Error(`Empilhado suporta até ${String(COR.serie.length)} fontes; recebidas ${String(fontes.length)}.`);
  const w = o.largura ?? 640;
  const h = TOPO + BAIXO + dados.length * LINHA;
  const total = (d: ReceitaPorFonte): number => Object.values(d.valores).reduce((a, b) => a + b, 0);
  const x = scaleLinear().domain([0, Math.max(1, ...dados.map(total))]).nice().range([ESQ, w - DIR]);
  const y = scaleBand<number>().domain(dados.map((_, i) => i)).range([TOPO, h - BAIXO]).padding(0.25);

  const svg = criarSvg(w, h, `${o.titulo}. Barras empilhadas de receita por fonte (${fontes.join(", ")}) para ${String(dados.length)} candidatos.`);
  const eixo = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  eixo.call(axisBottom(x).ticks(5, "~s"));
  eixo.selectAll("text").attr("fill", "var(--cor-texto-suave)");
  eixo.selectAll("path,line").attr("stroke", "var(--cor-borda)");

  dados.forEach((d, i) => {
    const yi = y(i) ?? 0;
    svg.append(textoSvg(ESQ - 6, yi + y.bandwidth() / 2 + 4, d.rotulo, { class: "rotulo", "text-anchor": "end" }));
    let acum = 0;
    fontes.forEach((f, k) => {
      const v = d.valores[f] ?? 0;
      if (v <= 0) return;
      const r = no("rect", { class: "marca", x: x(acum), y: yi, width: x(acum + v) - x(acum), height: y.bandwidth(), fill: COR.serie[k] ?? COR.principal, stroke: "var(--cor-fundo)" });
      marcaAcessivel(r, `${d.rotulo} — ${f}: ${formatarMoeda(v)}`);
      svg.append(r);
      acum += v;
    });
  });

  const legenda = document.createElement("ul");
  legenda.className = "legenda-grafico";
  fontes.forEach((f, k) => {
    const li = document.createElement("li");
    li.className = "legenda-item";
    const amostra = document.createElement("span");
    amostra.className = "amostra";
    amostra.style.background = COR.serie[k] ?? COR.principal;
    li.append(amostra, f);
    legenda.append(li);
  });

  container.replaceChildren(
    svg,
    legenda,
    tabelaAlternativa(o.titulo, ["Candidato", ...fontes, "Total"], dados.map((d) => [d.rotulo, ...fontes.map((f) => formatarMoeda(d.valores[f] ?? 0)), formatarMoeda(total(d))])),
  );
}

export function render(container: HTMLElement, dados: readonly ReceitaPorFonte[], opcoes: OpcoesEmpilhado): Grafico<readonly ReceitaPorFonte[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
