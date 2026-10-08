import { axisBottom, scaleBand, scaleLinear, select } from "d3";
import { formatarNumero } from "../../formato";
import { corpoRico, criarFlutuante } from "../ui/tooltip";
import { ligarMarca } from "../ui/tooltip";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico, substituir } from "./base";

export interface Barra {
  rotulo: string;
  valor: number;
  /** Linhas extras do tooltip (ex.: partido, UF); o título é o próprio rótulo. */
  detalhe?: readonly (readonly [rotulo: string, valor: string])[];
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

const ESQ_MIN = 150;
const DIR = 60;
const TOPO = 8;
const BAIXO = 28;
const LINHA = 26;
/**
 * Largura estimada do rótulo (12 px sans). Maiúsculas e dígitos são bem mais largos que minúsculas:
 * nomes de urna vêm em CAIXA ALTA, e a média única cortava o começo do nome no ranking.
 */
export function larguraEstimada(texto: string): number {
  let w = 0;
  for (const c of texto) w += c === " " ? 3.6 : /[A-ZÀ-Ý0-9]/.test(c) ? 8.2 : 6.4;
  return w;
}

/** Quebra por palavras em linhas de até `max` caracteres; palavra maior que `max` fica inteira (nunca corta). */
export function quebrarLinhas(texto: string, max: number): string[] {
  const linhas: string[] = [];
  let atual = "";
  for (const palavra of texto.split(/\s+/).filter(Boolean)) {
    if (atual === "") atual = palavra;
    else if ((atual + " " + palavra).length <= max) atual += " " + palavra;
    else { linhas.push(atual); atual = palavra; }
  }
  if (atual !== "") linhas.push(atual);
  return linhas.length > 0 ? linhas : [texto];
}

let balao: ReturnType<typeof criarFlutuante> | null = null;
/** Um balão para todas as barras (reaproveitado entre redesenhos). */
function tooltipBarras(): ReturnType<typeof criarFlutuante> {
  if (!balao || !balao.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

/** Desenha barras horizontais em `container` (substitui o conteúdo). */
export function desenhar(container: HTMLElement, dados: readonly Barra[], o: OpcoesBarras): void {
  if (dados.length === 0) { mensagemVazia(container); return; }
  const fmt = o.formato ?? formatarNumero;
  const w = o.largura ?? 640;
  
  const rot = (b: Barra, i: number): string => (o.prefixo ? o.prefixo(b, i) : "") + b.rotulo;
  // A margem esquerda acomoda o nome mais longo até 38% da largura; o que passar disso quebra em até 3 linhas.
  const maiorRotulo = Math.max(...dados.map((d, i) => larguraEstimada(rot(d, i))));
  const ESQ = Math.round(Math.min(Math.max(ESQ_MIN, maiorRotulo + 12), w * 0.38));
  // Caracteres que cabem na margem, medidos pela largura média do próprio texto desta lista.
  const mediaPx = maiorRotulo / Math.max(...dados.map((d, i) => rot(d, i).length));
  const maxChars = Math.max(10, Math.floor((ESQ - 12) / mediaPx));
  const linhasDe = dados.map((d, i) => quebrarLinhas(rot(d, i), maxChars));
  const alturaLinha = linhasDe.some((l) => l.length > 1) ? Math.max(LINHA, 14 * Math.max(...linhasDe.map((l) => l.length)) + 8) : LINHA;
  const h = TOPO + BAIXO + dados.length * alturaLinha;
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
    const linhas = linhasDe[i] ?? [rot(d, i)];
    const meio = yi + y.bandwidth() / 2 + 4;
    const rotuloSvg = textoSvg(ESQ - 6, meio - ((linhas.length - 1) * 14) / 2, "", { class: "rotulo", "text-anchor": "end" });
    linhas.forEach((l, k) => { rotuloSvg.append(no("tspan", { x: ESQ - 6, dy: k === 0 ? 0 : 14 }, l)); });
    svg.append(rotuloSvg);
    const r = no("rect", { class: "marca", x: ESQ, y: yi, width: larg, height: y.bandwidth(), fill: COR.principal });
    marcaAcessivel(r, `${rot(d, i)}: ${fmt(d.valor)}`);
    const linhasTip: [string, string][] = [...(d.detalhe ?? []).map(([a, b]): [string, string] => [a, b]), [o.colunaValor ?? "Valor", fmt(d.valor)]];
    r.dataset["tooltip"] = [d.rotulo, ...linhasTip.map(([a, b]) => `${a}: ${b}`)].join(" · ");
    ligarMarca(r, tooltipBarras(), () => corpoRico({ titulo: d.rotulo, linhas: linhasTip }));
    svg.append(r, textoSvg(ESQ + larg + 4, yi + y.bandwidth() / 2 + 4, fmt(d.valor), { class: "valor", "font-size": 11 }));
  });

  substituir(container, svg, tabelaAlternativa(o.titulo, ["Item", o.colunaValor ?? "Valor"], dados.map((d, i) => [rot(d, i), fmt(d.valor)])));
}

export function render(container: HTMLElement, dados: readonly Barra[], opcoes: OpcoesBarras): Grafico<readonly Barra[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
