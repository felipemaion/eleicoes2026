import { axisBottom, axisLeft, scaleBand, scaleLinear, select } from "d3";
import { formatarDecimal } from "../../formato";
import { corpoRico, criarFlutuante, ligarMarca } from "../ui/tooltip";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, substituir, tabelaAlternativa, textoSvg, type Grafico } from "./base";

/** Uma janela do calendário (antes/durante/depois) com a taxa do grupo e, se houver, a do candidato em foco. */
export interface JanelaRitmo {
  rotulo: string;
  /** Posts por semana; `null` = sem taxa (janela com menos de 7 dias), nunca zero. */
  grupo: number | null;
  candidato: number | null;
}

export interface OpcoesRitmo {
  titulo: string;
  /** Nome do candidato em foco (legenda e tooltip); sem ele só o grupo é desenhado. */
  nomeCandidato?: string;
  rotuloGrupo?: string;
  largura?: number;
  altura?: number;
}

const ESQ = 52;
const DIR = 16;
const TOPO = 24;
const BAIXO = 40;

let balao: ReturnType<typeof criarFlutuante> | null = null;
function tooltipRitmo(): ReturnType<typeof criarFlutuante> {
  if (!balao || !balao.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

const fmt = (v: number | null): string => (v === null ? "sem taxa semanal" : `${formatarDecimal(v)} posts/semana`);

function desenhar(container: HTMLElement, dados: readonly JanelaRitmo[], o: OpcoesRitmo): void {
  if (dados.every((d) => d.grupo === null && d.candidato === null)) { mensagemVazia(container); return; }
  const w = o.largura ?? 640;
  const h = o.altura ?? 300;
  const rotuloGrupo = o.rotuloGrupo ?? "Mediana do grupo";
  const series = [{ chave: "grupo" as const, nome: rotuloGrupo, cor: COR.principal }, ...(o.nomeCandidato ? [{ chave: "candidato" as const, nome: o.nomeCandidato, cor: COR.depois }] : [])];
  const max = Math.max(0.5, ...dados.flatMap((d) => [d.grupo ?? 0, d.candidato ?? 0]));
  const x0 = scaleBand().domain(dados.map((d) => d.rotulo)).range([ESQ, w - DIR]).paddingInner(0.25);
  const x1 = scaleBand().domain(series.map((s) => s.chave)).range([0, x0.bandwidth()]).padding(0.1);
  const y = scaleLinear().domain([0, max]).nice().range([h - BAIXO, TOPO]);

  const svg = criarSvg(w, h, `${o.titulo}. Barras de posts por semana em três janelas: ${dados.map((d) => `${d.rotulo}, ${rotuloGrupo} ${fmt(d.grupo)}${o.nomeCandidato ? `, ${o.nomeCandidato} ${fmt(d.candidato)}` : ""}`).join("; ")}.`);
  const gx = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`).call(axisBottom(x0));
  const gy = select(svg).append("g").attr("class", "eixo-y").attr("transform", `translate(${String(ESQ)},0)`).call(axisLeft(y).ticks(5).tickFormat((v) => formatarDecimal(+v)));
  for (const g of [gx, gy]) { g.selectAll("text").attr("fill", "var(--cor-texto-suave)"); g.selectAll("path,line").attr("stroke", "var(--cor-borda)"); }
  svg.append(textoSvg(14, h / 2, "Posts por semana", { "text-anchor": "middle", transform: `rotate(-90 14 ${String(h / 2)})` }));

  // Legenda dentro do SVG: a cor nunca é a única pista, o tooltip e a tabela repetem os nomes.
  series.forEach((s, i) => {
    svg.append(no("rect", { x: ESQ + i * 190, y: 4, width: 12, height: 12, fill: s.cor }), textoSvg(ESQ + i * 190 + 18, 15, s.nome, { "font-size": 12 }));
  });

  for (const d of dados) {
    for (const s of series) {
      const v = d[s.chave];
      const bx = (x0(d.rotulo) ?? 0) + (x1(s.chave) ?? 0);
      if (v === null) {
        // Janela sem taxa: marca de "n/d" no lugar da barra, para não parecer zero.
        svg.append(textoSvg(bx + x1.bandwidth() / 2, h - BAIXO - 6, "n/d", { class: "sem-taxa", "text-anchor": "middle", fill: "var(--cor-texto-suave)", "font-size": 11 }));
        continue;
      }
      const r = no("rect", { class: "marca", "data-serie": s.chave, "data-janela": d.rotulo, x: bx, y: y(v), width: x1.bandwidth(), height: Math.max(h - BAIXO - y(v), 1), fill: s.cor });
      marcaAcessivel(r, `${d.rotulo}, ${s.nome}: ${fmt(v)}`);
      r.dataset["tooltip"] = `${d.rotulo} · ${s.nome}: ${fmt(v)}`;
      ligarMarca(r, tooltipRitmo(), () => corpoRico({ titulo: s.nome, linhas: [["Janela", d.rotulo], ["Ritmo", fmt(v)]] }));
      svg.append(r, textoSvg(bx + x1.bandwidth() / 2, y(v) - 4, formatarDecimal(v), { class: "valor", "text-anchor": "middle", "font-size": 11 }));
    }
  }
  substituir(container, svg, tabelaAlternativa(o.titulo, ["Janela", rotuloGrupo, ...(o.nomeCandidato ? [o.nomeCandidato] : [])],
    dados.map((d) => [d.rotulo, fmt(d.grupo), ...(o.nomeCandidato ? [fmt(d.candidato)] : [])])));
}

export function render(container: HTMLElement, dados: readonly JanelaRitmo[], opcoes: OpcoesRitmo): Grafico<readonly JanelaRitmo[]> {
  const atual = opcoes;
  desenhar(container, dados, atual);
  return { atualizar: (n) => { desenhar(container, n, atual); }, destruir: () => { container.replaceChildren(); } };
}
