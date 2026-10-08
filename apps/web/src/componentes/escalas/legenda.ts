import { formatarDecimal } from "../../formato";
import { validarCoropletico, type Escala, type MetaIndicador } from "./escalas";

const SVG_NS = "http://www.w3.org/2000/svg";

function no<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}, texto?: string): SVGElementTagNameMap[K] {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (texto !== undefined) e.textContent = texto;
  return e;
}

export interface OpcoesLegenda {
  formatar?: (v: number) => string;
  largura?: number;
}

/** Legenda SVG da escala, sempre com unidade e denominador. Textos usam as variáveis do tema. */
export function criarLegenda(escala: Escala, meta: MetaIndicador, opcoes: OpcoesLegenda = {}): SVGSVGElement {
  validarCoropletico(meta);
  const fmt = opcoes.formatar ?? formatarDecimal;
  const largura = opcoes.largura ?? 380;
  const n = escala.cores.length;
  const w = (largura - 100) / n; // sobra espaço à direita para "sem dado" não ser cortado
  const svg = no("svg", { width: largura, height: 74, viewBox: `0 0 ${String(largura)} 74`, role: "img", class: "legenda" });

  const faixas = escala.cores.map((_, i) => {
    const ini = i === 0 ? "menor que" : `de ${fmt(escala.quebras[i - 1] ?? 0)}`;
    return i === n - 1 ? `${ini} em diante` : i === 0 ? `${ini} ${fmt(escala.quebras[0] ?? 0)}` : `${ini} a menos de ${fmt(escala.quebras[i] ?? 0)}`;
  });
  svg.append(
    no("title", {}, `Legenda: ${meta.nome}`),
    no("desc", {}, `${meta.unidade}; denominador: ${meta.denominador}. Faixas: ${faixas.join("; ")}.`),
    no("text", { x: 0, y: 12, class: "legenda-unidade", fill: "var(--cor-texto)", "font-size": 12 }, `${meta.nome} (${meta.unidade})`),
    no("text", { x: 0, y: 26, class: "legenda-denominador", fill: "var(--cor-texto-suave)", "font-size": 11 }, `Denominador: ${meta.denominador}`),
  );
  escala.cores.forEach((cor, i) => {
    svg.append(no("rect", { class: "classe", x: i * w, y: 34, width: w, height: 12, fill: cor, stroke: "var(--cor-borda)" }));
  });
  escala.quebras.forEach((q, i) => {
    svg.append(no("text", { class: "quebra", x: (i + 1) * w, y: 62, "text-anchor": "middle", fill: "var(--cor-texto)", "font-size": 11 }, fmt(q)));
  });
  svg.append(
    no("rect", { class: "sem-dado", x: n * w + 12, y: 34, width: 12, height: 12, fill: "var(--cor-sem-dado)", stroke: "var(--cor-borda)" }),
    no("text", { x: n * w + 28, y: 44, fill: "var(--cor-texto)", "font-size": 11 }, "sem dado"),
  );
  return svg;
}
