import { axisBottom, axisLeft, extent, line, scaleLinear, scaleTime, select } from "d3";
import { formatarNumero, formatarVariacao } from "../../formato";
import { corpoRico, criarFlutuante, ligarMarca } from "../ui/tooltip";
import { PALETAS } from "../../paletas";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, substituir, tabelaAlternativa, textoSvg, type Grafico } from "./base";

export interface PontoTempo {
  /** ISO 8601 (UTC). */
  quando: string;
  valor: number;
  /** Mudança desde a coleta anterior (campos da API; `abs: null` no 1º ponto). Opcional: sem ela o gráfico não rotula trechos. */
  variacao?: { abs: number | null; pct: number | null; dias: number | null };
}

export interface OpcoesSerie {
  titulo: string;
  /** Nome do que se mede (ex.: "Seguidores"). */
  medida: string;
  largura?: number;
  altura?: number;
}

const ESQ = 70;
const DIR = 24;
const TOPO = 16;
const BAIXO = 40;

/** Alta e queda: azul e vermelhão do Okabe-Ito (seguros para daltônicos); o sinal no texto repete a direção. */
const COR_VARIACAO = { alta: PALETAS.categorica[5], queda: PALETAS.categorica[6], neutra: "var(--cor-texto-suave)" } as const;
/** Largura estimada por caractere (fonte 12 px) e respiro: abaixo disso o rótulo não cabe no trecho. */
const PX_POR_CARACTERE = 6.6;
const RESPIRO = 10;

const dia = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric" });
const diaMes = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit" });

let balao: ReturnType<typeof criarFlutuante> | null = null;
function tooltipSerie(): ReturnType<typeof criarFlutuante> {
  if (!balao || !balao.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

/** Rótulo no meio de cada trecho, acima da linha; trecho estreito demais fica sem rótulo (a variação segue no tooltip e na tabela). */
function rotularTrechos(svg: SVGSVGElement, dados: readonly PontoTempo[], x: (d: Date) => number, y: (v: number) => number): void {
  for (let i = 1; i < dados.length; i++) {
    const a = dados[i - 1];
    const b = dados[i];
    const texto = b?.variacao ? formatarVariacao(b.variacao) : null;
    if (!a || !b || texto === null || !b.variacao) continue;
    const xa = x(new Date(a.quando));
    const xb = x(new Date(b.quando));
    if (xb - xa < texto.length * PX_POR_CARACTERE + RESPIRO) continue;
    const sentido = (b.variacao.abs ?? 0) > 0 ? "alta" : (b.variacao.abs ?? 0) < 0 ? "queda" : "neutra";
    svg.append(textoSvg((xa + xb) / 2, Math.max(TOPO - 4, (y(a.valor) + y(b.valor)) / 2 - 10), texto, {
      class: `variacao-trecho ${sentido}`, "text-anchor": "middle", fill: COR_VARIACAO[sentido], "font-weight": 600,
      stroke: "var(--cor-superficie)", "stroke-width": 3, "paint-order": "stroke",
    }));
  }
}

/** Linha de uma série curta (dias): eixo vertical ajustado ao intervalo, porque linha — ao contrário de barra — não precisa partir do zero. */
function desenhar(container: HTMLElement, dados: readonly PontoTempo[], o: OpcoesSerie): void {
  if (dados.length < 2) { mensagemVazia(container); return; }
  const w = o.largura ?? 640;
  const h = o.altura ?? 280;
  const datas = dados.map((d) => new Date(d.quando));
  const [t0, t1] = extent(datas) as [Date, Date];
  const [v0, v1] = extent(dados, (d) => d.valor) as [number, number];
  const folga = Math.max((v1 - v0) * 0.2, v1 * 0.002, 1);
  const x = scaleTime().domain([t0, t1]).range([ESQ, w - DIR]);
  const y = scaleLinear().domain([v0 - folga, v1 + folga]).nice().range([h - BAIXO, TOPO]);

  const svg = criarSvg(w, h, `${o.titulo}. Linha com ${String(dados.length)} coletas, de ${formatarNumero(dados[0]?.valor ?? 0)} em ${dia.format(t0)} a ${formatarNumero(dados[dados.length - 1]?.valor ?? 0)} em ${dia.format(t1)}.`);
  const gx = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`).call(axisBottom(x).ticks(Math.min(dados.length, 6)).tickFormat((d) => diaMes.format(d as Date)));
  const gy = select(svg).append("g").attr("class", "eixo-y").attr("transform", `translate(${String(ESQ)},0)`).call(axisLeft(y).ticks(5).tickFormat((v) => formatarNumero(+v)));
  for (const g of [gx, gy]) { g.selectAll("text").attr("fill", "var(--cor-texto-suave)"); g.selectAll("path,line").attr("stroke", "var(--cor-borda)"); }
  svg.append(textoSvg(14, h / 2, o.medida, { "text-anchor": "middle", transform: `rotate(-90 14 ${String(h / 2)})` }));
  const caminho = line<PontoTempo>().x((d) => x(new Date(d.quando))).y((d) => y(d.valor))(dados);
  svg.append(no("path", { class: "linha-serie", d: caminho ?? "", fill: "none", stroke: COR.principal, "stroke-width": 2 }));
  rotularTrechos(svg, dados, x, y);
  for (const d of dados) {
    const c = no("circle", { class: "marca", cx: x(new Date(d.quando)), cy: y(d.valor), r: 5, fill: COR.principal, stroke: "var(--cor-superficie)", "stroke-width": 1.5 });
    const variacao = d.variacao ? formatarVariacao(d.variacao) : null;
    marcaAcessivel(c, `${dia.format(new Date(d.quando))}: ${formatarNumero(d.valor)} ${o.medida.toLowerCase()}${variacao ? `, variação ${variacao}` : ""}`);
    c.dataset["tooltip"] = `${dia.format(new Date(d.quando))} · ${o.medida}: ${formatarNumero(d.valor)}${variacao ? ` · Variação: ${variacao}` : ""}`;
    ligarMarca(c, tooltipSerie(), () => corpoRico({ titulo: dia.format(new Date(d.quando)), linhas: [[o.medida, formatarNumero(d.valor)], ...(variacao ? [["Variação", variacao] as const] : [])] }));
    svg.append(c);
  }
  const comVariacao = dados.some((d) => d.variacao !== undefined);
  substituir(container, svg, tabelaAlternativa(
    o.titulo,
    ["Coleta", o.medida, ...(comVariacao ? ["Variação"] : [])],
    dados.map((d) => [dia.format(new Date(d.quando)), formatarNumero(d.valor), ...(comVariacao ? [(d.variacao ? formatarVariacao(d.variacao) : null) ?? "—"] : [])]),
  ));
}

export function render(container: HTMLElement, dados: readonly PontoTempo[], opcoes: OpcoesSerie): Grafico<readonly PontoTempo[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
