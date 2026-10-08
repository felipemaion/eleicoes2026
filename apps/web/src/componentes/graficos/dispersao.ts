import { axisBottom, axisLeft, scaleLog, select, type ScaleLogarithmic } from "d3";
import { formatarCompacto, formatarMoeda, formatarNumero } from "../../formato";
import { abrirNoTse, avisoLinkTse, type LinkTse } from "../ui/foto-candidato";
import { corpoRico, criarFlutuante, ligarMarca } from "../ui/tooltip";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico, substituir } from "./base";

export interface PontoCustoVoto {
  id: string;
  rotulo: string;
  custo: number;
  votos: number;
  /** Linhas do tooltip (rótulo, valor); o título é o próprio rótulo. */
  detalhe?: readonly (readonly [string, string])[];
  /** URL da foto; `null` = candidatura sem foto (placeholder); ausente = o tooltip não mostra foto. */
  foto?: string | null;
  /** Página do candidato no TSE: clique/Enter no círculo abre em nova aba. */
  linkTse?: LinkTse;
}

export interface OpcoesDispersao {
  titulo: string;
  largura?: number;
  altura?: number;
  /** Ids realçados (ex.: resultado da busca); os demais ficam atenuados. */
  destaque?: ReadonlySet<string>;
  /** Linha de custo por voto constante (votos = custo ÷ cpv; reta de inclinação 1 em escala log-log). */
  referencia?: { custoPorVoto: number; rotulo: string };
}

export interface GraficoDispersao extends Grafico<readonly PontoCustoVoto[]> {
  /** Troca os realçados sem redesenhar (preserva foco e tooltip). */
  destacar(ids: ReadonlySet<string>): void;
}

let balao: ReturnType<typeof criarFlutuante> | null = null;
function tooltipDispersao(): ReturnType<typeof criarFlutuante> {
  if (!balao || !balao.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

function aplicarDestaque(raiz: ParentNode, ids: ReadonlySet<string>): void {
  const ativo = ids.size > 0;
  raiz.querySelectorAll<SVGElement>("circle.marca").forEach((c) => {
    const quer = ativo && ids.has(c.dataset["id"] ?? "");
    c.classList.toggle("destaque", quer);
    c.classList.toggle("atenuado", ativo && !quer);
    c.setAttribute("r", quer ? "8" : "5");
  });
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

function desenharReferencia(svg: SVGSVGElement, x: ScaleLogarithmic<number, number>, y: ScaleLogarithmic<number, number>, ref: { custoPorVoto: number; rotulo: string }): void {
  const [x0, x1] = x.domain() as [number, number];
  const [y0, y1] = y.domain() as [number, number];
  // Recorta a reta ao retângulo do gráfico, no espaço dos dados: custo = cpv × votos.
  const ini = Math.max(x0, y0 * ref.custoPorVoto);
  const fim = Math.min(x1, y1 * ref.custoPorVoto);
  if (ini >= fim) return;
  svg.append(
    no("line", { class: "referencia", x1: x(ini), y1: y(ini / ref.custoPorVoto), x2: x(fim), y2: y(fim / ref.custoPorVoto), stroke: "var(--cor-texto-suave)", "stroke-width": 1.5, "stroke-dasharray": "6 4" }),
    textoSvg(x(fim) - 4, y(fim / ref.custoPorVoto) - 6, ref.rotulo, { class: "referencia-rotulo", "text-anchor": "end", fill: "var(--cor-texto-suave)" }),
  );
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

  if (o.referencia && o.referencia.custoPorVoto > 0) desenharReferencia(svg, x, y, o.referencia);
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
    const linhas = [...(d.detalhe ?? [["Custo", formatarMoeda(d.custo)], ["Votos", formatarNumero(d.votos)]]), ...(aviso ? [["Atenção", aviso] as const] : [])];
    c.dataset["tooltip"] = [d.rotulo, ...linhas.map(([a, b]) => `${a}: ${b}`)].join(" · ");
    const link = d.linkTse;
    ligarMarca(c, tooltipDispersao(), () => corpoRico({
      titulo: d.rotulo, linhas,
      ...(d.foto !== undefined ? { foto: { nome: d.rotulo, url: d.foto } } : {}),
      ...(link ? { rodape: avisoLinkTse(link) } : {}),
    }));
    if (link) {
      c.setAttribute("role", "link");
      c.classList.add("com-link");
      c.addEventListener("click", () => { abrirNoTse(link.url); });
      c.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); abrirNoTse(link.url); } });
    }
    svg.append(c);
  }

  aplicarDestaque(svg, o.destaque ?? new Set());
  substituir(container,
    svg,
    ...(o.referencia ? [Object.assign(document.createElement("p"), { className: "nota", textContent: `Linha tracejada: ${o.referencia.rotulo}. Acima dela, o candidato rendeu mais votos por real que a mediana.` })] : []),
    tabelaAlternativa(o.titulo, ["Candidato", "Custo", "Votos", "Observação"], dados.map((d) => [d.rotulo, formatarMoeda(d.custo), formatarNumero(d.votos), d.custo <= 0 || d.votos <= 0 ? "valor zero fora da escala log" : ""])),
  );
}

export function render(container: HTMLElement, dados: readonly PontoCustoVoto[], opcoes: OpcoesDispersao): GraficoDispersao {
  let atual: OpcoesDispersao = opcoes;
  desenhar(container, dados, atual);
  return {
    atualizar: (n) => { desenhar(container, n, atual); },
    destacar: (ids) => { atual = { ...atual, destaque: ids }; aplicarDestaque(container, ids); },
    destruir: () => { container.replaceChildren(); },
  };
}
