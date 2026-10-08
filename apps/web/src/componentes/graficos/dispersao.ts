import { axisBottom, axisLeft, scaleLog, select } from "d3";
import { formatarCompacto, formatarMoeda, formatarNumero } from "../../formato";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico, substituir } from "./base";

export interface PontoCustoVoto {
  id: string;
  rotulo: string;
  custo: number;
  votos: number;
}

export interface OpcoesDispersao {
  titulo: string;
  largura?: number;
  altura?: number;
}

const ESQ = 76;
const DIR = 20;
const TOPO = 12;
const BAIXO = 48;
/** Largura da "calha": log(0) não existe, então zeros ficam numa faixa separada, marcados. */
const CALHA = 26;

function dominioLog(valores: readonly number[]): [number, number] {
  const positivos = valores.filter((v) => v > 0);
  if (positivos.length === 0) return [1, 10];
  const min = Math.min(...positivos);
  const max = Math.max(...positivos);
  return min === max ? [min / 2, max * 2] : [min, max];
}

function desenhar(container: HTMLElement, dados: readonly PontoCustoVoto[], o: OpcoesDispersao): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const w = o.largura ?? 640;
  const h = o.altura ?? 420;
  const x = scaleLog().domain(dominioLog(dados.map((d) => d.custo))).range([ESQ + CALHA, w - DIR]).nice();
  const y = scaleLog().domain(dominioLog(dados.map((d) => d.votos))).range([h - BAIXO - CALHA, TOPO]).nice();
  const xZero = ESQ + CALHA / 2 - 4;
  const yZero = h - BAIXO - CALHA / 2 + 4;
  const nZero = dados.filter((d) => d.custo <= 0 || d.votos <= 0).length;

  const svg = criarSvg(
    w,
    h,
    `${o.titulo}. Dispersão de ${String(dados.length)} candidatos, custo de campanha (eixo horizontal) por votos (eixo vertical), ambos em escala logarítmica.` +
      (nZero > 0 ? ` ${String(nZero)} com custo ou votos zero, marcados à parte na faixa "0".` : ""),
  );
  const gx = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  gx.call(axisBottom(x).ticks(5).tickFormat((v) => formatarCompacto(+v)));
  const gy = select(svg).append("g").attr("class", "eixo-y").attr("transform", `translate(${String(ESQ)},0)`);
  gy.call(axisLeft(y).ticks(5).tickFormat((v) => formatarCompacto(+v)));
  for (const g of [gx, gy]) {
    g.selectAll("text").attr("fill", "var(--cor-texto-suave)");
    g.selectAll("path,line").attr("stroke", "var(--cor-borda)");
  }
  svg.append(
    textoSvg(xZero, h - BAIXO + 16, "0", { class: "tick-zero", "text-anchor": "middle", fill: "var(--cor-texto-suave)" }),
    textoSvg(ESQ - 8, yZero, "0", { class: "tick-zero", "text-anchor": "end", fill: "var(--cor-texto-suave)" }),
    textoSvg((ESQ + w - DIR) / 2, h - 6, "Custo de campanha (R$, escala log)", { "text-anchor": "middle" }),
    textoSvg(14, h / 2, "Votos (escala log)", { "text-anchor": "middle", transform: `rotate(-90 14 ${String(h / 2)})` }),
  );

  for (const d of dados) {
    const zeroX = d.custo <= 0;
    const zeroY = d.votos <= 0;
    const c = no("circle", {
      class: zeroX || zeroY ? "marca zero" : "marca",
      "data-id": d.id,
      cx: zeroX ? xZero : x(d.custo),
      cy: zeroY ? yZero : y(d.votos),
      r: 5,
      fill: zeroX || zeroY ? "none" : COR.principal,
      stroke: zeroX || zeroY ? COR.zero : COR.principal,
      "stroke-width": 2,
    });
    const aviso = [zeroX ? "custo zero" : "", zeroY ? "votos zero" : ""].filter(Boolean).join(", ");
    marcaAcessivel(c, `${d.rotulo}: ${formatarMoeda(d.custo)}, ${formatarNumero(d.votos)} votos${aviso ? ` (${aviso})` : ""}`);
    svg.append(c);
  }

  substituir(container,
    svg,
    tabelaAlternativa(o.titulo, ["Candidato", "Custo", "Votos", "Observação"], dados.map((d) => [d.rotulo, formatarMoeda(d.custo), formatarNumero(d.votos), d.custo <= 0 || d.votos <= 0 ? "valor zero fora da escala log" : ""])),
  );
}

export function render(container: HTMLElement, dados: readonly PontoCustoVoto[], opcoes: OpcoesDispersao): Grafico<readonly PontoCustoVoto[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
