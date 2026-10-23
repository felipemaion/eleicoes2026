import { axisBottom, axisLeft, scaleLog, select, type ScaleLogarithmic } from "d3";
import { PALETAS } from "../../paletas";
import { formatarCompacto, formatarMoeda, formatarNumero } from "../../formato";
import { abrirNoTse, avisoLinkTse, type LinkTse } from "../ui/foto-candidato";
import { corpoRico, criarFlutuante, ligarMarca, type Flutuante } from "../ui/tooltip";
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
  /**
   * Outro destino externo (ex.: perfil no Instagram); `convite` é a linha do tooltip que avisa do clique.
   * Com `aoSelecionar`, o clique não abre o destino: ele vira o link `texto` dentro do tooltip fixo.
   */
  linkExterno?: { url: string; convite: string; texto?: string };
  /** Valor do eixo vertical quando não são os votos (ex.: despesa por voto); sem ele o eixo é `votos`. */
  y?: number;
  /** Posição em relação ao esperado: muda a cor do círculo (o texto do tooltip diz o mesmo). */
  classe?: "acima" | "abaixo" | "neutro";
}

export interface OpcoesDispersao {
  titulo: string;
  largura?: number;
  altura?: number;
  /** Ids realçados (ex.: resultado da busca); os demais ficam atenuados. */
  destaque?: ReadonlySet<string>;
  /** Linha de custo por voto constante (votos = custo ÷ cpv; reta de inclinação 1 em escala log-log). */
  referencia?: { custoPorVoto: number; rotulo: string };
  /** O que o eixo horizontal mede ("custo de campanha" por padrão; "receita de campanha" na dispersão de receitas). */
  grandeza?: string;
  /** Formata o eixo horizontal e os valores do tooltip/tabela (padrão: moeda). */
  formatoX?: (v: number) => string;
  /** Texto completo do título do eixo horizontal (padrão: "<grandeza> (R$, escala log)"). */
  rotuloEixoX?: string;
  /** Eixo vertical alternativo ao de votos: título do eixo, nome da coluna da tabela, formatador e descrição para leitores de tela. */
  eixoY?: { rotulo: string; coluna: string; formato: (v: number) => string; descricao: string };
  /** Diagonal y = x tracejada (mesma unidade nos dois eixos, ex.: "gastou o que arrecadou"). */
  diagonal?: { rotulo: string };
  /** Linha de tendência `log10(1+y) = a + b·log10(1+x)` desenhada sobre a nuvem. */
  reta?: { intercepto: number; inclinacao: number; rotulo: string };
  /** Nota de rodapé sobre a linha de referência (padrão fala de custo por voto). */
  notaReferencia?: string;
  /**
   * Opt-in (tela de Redes): clique/Enter/Espaço no ponto chama `aoSelecionar(id)` e fixa o tooltip,
   * com o `linkExterno` como link de nova aba. Sem esta opção o clique abre o link direto (Gastos, Receitas).
   */
  aoSelecionar?: (id: string) => void;
}

export interface GraficoDispersao extends Grafico<readonly PontoCustoVoto[]> {
  /** Troca os realçados sem redesenhar (preserva foco e tooltip). */
  destacar(ids: ReadonlySet<string>): void;
}

let balao: Flutuante | null = null;
function tooltipDispersao(): Flutuante {
  if (!balao || !balao.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

/**
 * Ponto cujo tooltip está fixo (modo de seleção). Um só por página porque o balão é compartilhado;
 * mesmo comportamento de `ligarPainel`: segundo clique, Esc ou clique fora fecham.
 */
let fixo: SVGElement | null = null;
/** Devolver o foco ao ponto depois do Esc não deve reabrir o balão de hover. */
let devolvendoFoco = false;

function soltar(devolverFoco = false): void {
  if (fixo === null) return;
  const marca = fixo;
  fixo = null;
  marca.setAttribute("aria-expanded", "false");
  const b = tooltipDispersao();
  b.elemento.classList.remove("fixo");
  b.elemento.setAttribute("role", "tooltip");
  b.elemento.removeAttribute("aria-label");
  b.esconder();
  if (devolverFoco) {
    devolvendoFoco = true;
    marca.focus();
    devolvendoFoco = false;
  }
}

function fixar(marca: SVGElement, rotulo: string, conteudo: Node): void {
  const b = tooltipDispersao();
  const r = marca.getBoundingClientRect();
  b.mostrar(conteudo, { x: r.left, y: r.top, largura: r.width, altura: r.height });
  b.elemento.classList.add("fixo");
  // Com link dentro, o balão deixa de ser só descrição: vira um diálogo não modal.
  b.elemento.setAttribute("role", "dialog");
  b.elemento.setAttribute("aria-label", rotulo);
  marca.setAttribute("aria-expanded", "true");
  fixo = marca;
}

let globaisLigados = false;
function ligarGlobais(): void {
  if (globaisLigados) return;
  globaisLigados = true;
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || fixo === null) return;
    const ativo = document.activeElement;
    const focoNele = ativo === fixo || (ativo !== null && tooltipDispersao().elemento.contains(ativo));
    soltar(focoNele);
  });
  document.addEventListener("pointerdown", (e) => {
    if (fixo === null || !(e.target instanceof Node)) return;
    if (e.target === fixo || tooltipDispersao().elemento.contains(e.target)) return;
    soltar();
  });
}

/** Balão para `ligarMarca`: hover e foco não mexem nele enquanto há um tooltip fixo. */
const balaoDeHover: Flutuante = {
  get elemento() { return tooltipDispersao().elemento; },
  mostrar(conteudo, ancora) { if (fixo === null && !devolvendoFoco) tooltipDispersao().mostrar(conteudo, ancora); },
  mover(ancora) { if (fixo === null) tooltipDispersao().mover(ancora); },
  esconder() { if (fixo === null) tooltipDispersao().esconder(); },
};

/** Liga clique/teclado de seleção a um ponto: seleciona, fixa o tooltip e põe o link externo dentro dele. */
function ligarSelecao(c: SVGElement, d: PontoCustoVoto, conteudoBase: () => DocumentFragment, aoSelecionar: (id: string) => void): void {
  ligarGlobais();
  const externo = d.linkExterno;
  const url = externo?.url.startsWith("https://") ? externo.url : null;
  let ancora: HTMLAnchorElement | null = null;
  const conteudo = (): Node => {
    const f = conteudoBase();
    if (url !== null) {
      ancora = Object.assign(document.createElement("a"), { href: url, target: "_blank", rel: "noopener noreferrer", textContent: externo?.texto ?? "Abrir link (nova aba)" });
      ancora.addEventListener("keydown", (e) => {
        if (e.key !== "Tab") return;
        e.preventDefault();
        if (e.shiftKey) { c.focus(); return; }
        // Tab adiante: fecha o balão e segue para o próximo ponto, como se o link estivesse logo depois dele.
        const proximo = c.nextElementSibling instanceof SVGElement && c.nextElementSibling.matches("circle.marca") ? c.nextElementSibling : c;
        soltar();
        proximo.focus();
      });
      const p = h("p", "tooltip-rodape tooltip-link");
      p.append(ancora);
      f.append(p);
    }
    f.append(h("p", "tooltip-rodape", "Esc ou clique fora para fechar."));
    return f;
  };
  const alternar = (): void => {
    if (fixo === c) { soltar(); return; }
    soltar();
    aoSelecionar(d.id);
    fixar(c, d.rotulo, conteudo());
  };
  c.setAttribute("role", "button");
  c.setAttribute("aria-label", `${c.getAttribute("aria-label") ?? d.rotulo}. Ao ativar, abre os dados${url !== null ? " e o link do perfil" : ""}.`);
  c.setAttribute("aria-expanded", "false");
  c.setAttribute("aria-controls", tooltipDispersao().elemento.id);
  c.classList.add("com-link");
  c.addEventListener("click", alternar);
  // Foco chegando a outro ponto (Shift+Tab, clique) solta o balão fixo do anterior.
  c.addEventListener("focus", () => { if (fixo !== null && fixo !== c && !devolvendoFoco) soltar(); });
  c.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alternar(); return; }
    if (e.key === "Tab" && !e.shiftKey && fixo === c && ancora?.isConnected) { e.preventDefault(); ancora.focus(); }
  });
}

function h(tag: "p", classe: string, texto?: string): HTMLElement {
  const el = document.createElement(tag);
  el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
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

/** Em escala log o D3 enche o eixo de 2…9 por década e os rótulos se sobrepõem: ficam só 1, 2 e 5. */
const ticksLegiveis = (e: ScaleLogarithmic<number, number>): number[] => e.ticks().filter((t) => /^[125]/.test(String(t)));

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

/** Diagonal y = x recortada ao retângulo comum dos dois domínios (inclinação 1 em log-log). */
function desenharDiagonal(svg: SVGSVGElement, x: ScaleLogarithmic<number, number>, y: ScaleLogarithmic<number, number>, rotulo: string): void {
  const [x0, x1] = x.domain() as [number, number];
  const [y0, y1] = y.domain() as [number, number];
  const ini = Math.max(x0, y0);
  const fim = Math.min(x1, y1);
  if (ini >= fim) return;
  svg.append(
    no("line", { class: "referencia", x1: x(ini), y1: y(ini), x2: x(fim), y2: y(fim), stroke: "var(--cor-texto-suave)", "stroke-width": 1.5, "stroke-dasharray": "6 4" }),
    textoSvg(x(fim) - 4, y(fim) - 6, rotulo, { class: "referencia-rotulo", "text-anchor": "end", fill: "var(--cor-texto-suave)" }),
  );
}

/** Reta do ajuste log-log: amostrada, porque o "1 +" a deixa levemente curva nos eixos logarítmicos. */
function desenharReta(svg: SVGSVGElement, x: ScaleLogarithmic<number, number>, y: ScaleLogarithmic<number, number>, r: { intercepto: number; inclinacao: number; rotulo: string }): void {
  const [x0, x1] = x.domain() as [number, number];
  const pontos: string[] = [];
  const [y0, y1] = y.domain() as [number, number];
  for (let i = 0; i <= 40; i++) {
    const sx = x0 * Math.pow(x1 / x0, i / 40);
    const sy = Math.pow(10, r.intercepto + r.inclinacao * Math.log10(1 + sx)) - 1;
    if (sy >= y0 && sy <= y1) pontos.push(`${String(x(sx))},${String(y(sy))}`);
  }
  if (pontos.length < 2) return;
  const ultimo = pontos[pontos.length - 1]?.split(",") ?? ["0", "0"];
  svg.append(
    no("polyline", { class: "reta-ajuste", points: pontos.join(" "), fill: "none", stroke: "var(--cor-texto-suave)", "stroke-width": 1.5, "stroke-dasharray": "6 4" }),
    textoSvg(Number(ultimo[0]) - 4, Number(ultimo[1]) - 6, r.rotulo, { class: "referencia-rotulo", "text-anchor": "end", fill: "var(--cor-texto-suave)" }),
  );
}

/** Divergente seguro para daltônicos (azul × vermelhão do Okabe-Ito) em torno de um cinza neutro: o texto do tooltip repete a posição. */
const COR_CLASSE = { acima: PALETAS.categorica[5], abaixo: PALETAS.categorica[6], neutro: "var(--cor-texto-suave)" } as const;

function desenhar(container: HTMLElement, dados: readonly PontoCustoVoto[], o: OpcoesDispersao): void {
  // Redesenho apaga o ponto fixado: o balão não pode ficar apontando para um elemento que saiu do DOM.
  if (fixo !== null && container.contains(fixo)) soltar();
  if (dados.length === 0) { mensagemVazia(container); return; }
  const w = o.largura ?? 640;
  const h = o.altura ?? 420;
  const x = scaleLog().domain(dominioLog(dados.map((d) => d.custo))).range([ESQ + CALHA, w - DIR]).nice();
  const valorY = (d: PontoCustoVoto): number => d.y ?? d.votos;
  const eixoY = o.eixoY;
  const y = scaleLog().domain(dominioLog(dados.map(valorY))).range([h - BAIXO - CALHA, TOPO]).nice();
  const xZero = ESQ + CALHA / 2 - 4;
  const yZero = h - BAIXO - CALHA / 2 + 4;
  const grandeza = o.grandeza ?? "custo de campanha";
  const Grandeza = grandeza.charAt(0).toUpperCase() + grandeza.slice(1);
  const palavra = grandeza.split(" ")[0] ?? "valor";
  const fmtX = o.formatoX ?? formatarMoeda;
  const fmtY = eixoY?.formato ?? formatarNumero;
  const nomeY = eixoY?.descricao ?? "votos";
  const nZero = dados.filter((d) => d.custo <= 0 || valorY(d) <= 0).length;

  const svg = criarSvg(
    w,
    h,
    `${o.titulo}. Dispersão de ${String(dados.length)} candidatos, ${grandeza} (eixo horizontal) por ${nomeY} (eixo vertical), ambos em escala logarítmica.` +
      (nZero > 0 ? ` ${String(nZero)} com ${palavra} ou ${nomeY} zero, marcados à parte na faixa "0".` : ""),
  );
  const gx = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  gx.call(axisBottom(x).tickValues(ticksLegiveis(x)).tickFormat((v) => formatarCompacto(+v)));
  const gy = select(svg).append("g").attr("class", "eixo-y").attr("transform", `translate(${String(ESQ)},0)`);
  gy.call(axisLeft(y).tickValues(ticksLegiveis(y)).tickFormat((v) => formatarCompacto(+v)));
  for (const g of [gx, gy]) {
    g.selectAll("text").attr("fill", "var(--cor-texto-suave)");
    g.selectAll("path,line").attr("stroke", "var(--cor-borda)");
  }
  svg.append(
    textoSvg(xZero, h - BAIXO + 16, "0", { class: "tick-zero", "text-anchor": "middle", fill: "var(--cor-texto-suave)" }),
    textoSvg(ESQ - 8, yZero, "0", { class: "tick-zero", "text-anchor": "end", fill: "var(--cor-texto-suave)" }),
    textoSvg((ESQ + w - DIR) / 2, h - 6, o.rotuloEixoX ?? `${Grandeza} (R$, escala log)`, { "text-anchor": "middle" }),
    textoSvg(14, h / 2,  eixoY?.rotulo ?? "Votos (escala log)", { "text-anchor": "middle", transform: `rotate(-90 14 ${String(h / 2)})` }),
  );

  if (o.referencia && o.referencia.custoPorVoto > 0) desenharReferencia(svg, x, y, o.referencia);
  if (o.diagonal) desenharDiagonal(svg, x, y, o.diagonal.rotulo);
  if (o.reta) desenharReta(svg, x, y, o.reta);
  for (const d of dados) {
    const zeroX = d.custo <= 0;
    const zeroY = valorY(d) <= 0;
    const c = no("circle", {
      class: zeroX || zeroY ? "marca zero" : "marca",
      "data-id": d.id,
      cx: zeroX ? xZero : x(d.custo),
      cy: zeroY ? yZero : y(valorY(d)),
      r: 5,
      fill: zeroX || zeroY ? "none" : COR_CLASSE[d.classe ?? "neutro"],
      stroke: zeroX || zeroY ? COR.zero : COR_CLASSE[d.classe ?? "neutro"],
      "stroke-width": 2,
    });
    const aviso = [zeroX ? `${palavra} zero` : "", zeroY ? `${nomeY} zero` : ""].filter(Boolean).join(", ");
    marcaAcessivel(c, eixoY
      ? `${d.rotulo}: ${fmtX(d.custo)}, ${fmtY(valorY(d))} (${nomeY})${aviso ? ` (${aviso})` : ""}`
      : `${d.rotulo}: ${fmtX(d.custo)}, ${formatarNumero(d.votos)} votos${aviso ? ` (${aviso})` : ""}`);
    const linhas = [...(d.detalhe ?? [[Grandeza.split(" ")[0] ?? "Custo", fmtX(d.custo)], [eixoY?.coluna ?? "Votos", fmtY(valorY(d))]]), ...(aviso ? [["Atenção", aviso] as const] : [])];
    c.dataset["tooltip"] = [d.rotulo, ...linhas.map(([a, b]) => `${a}: ${b}`)].join(" · ");
    const link = d.linkTse;
    const externo = d.linkExterno;
    const base = (rodape: boolean): DocumentFragment => corpoRico({
      titulo: d.rotulo, linhas,
      ...(d.foto !== undefined ? { foto: { nome: d.rotulo, url: d.foto } } : {}),
      ...(!rodape ? {} : link ? { rodape: avisoLinkTse(link) } : externo ? { rodape: [externo.convite] } : {}),
    });
    const aoSelecionar = o.aoSelecionar;
    // A seleção liga seus ouvintes de foco antes de `ligarMarca`, para soltar o balão fixo antes do hover reagir.
    if (aoSelecionar) ligarSelecao(c, d, () => base(false), aoSelecionar);
    ligarMarca(c, balaoDeHover, () => base(true));
    const destino = link?.url ?? externo?.url;
    if (destino !== undefined && !aoSelecionar) {
      c.setAttribute("role", "link");
      c.classList.add("com-link");
      c.addEventListener("click", () => { abrirNoTse(destino); });
      c.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); abrirNoTse(destino); } });
    }
    svg.append(c);
  }

  aplicarDestaque(svg, o.destaque ?? new Set());
  substituir(container,
    svg,
    ...(o.diagonal ? [Object.assign(document.createElement("p"), { className: "nota", textContent: `Linha tracejada: ${o.diagonal.rotulo}.` })] : []),
    ...(o.referencia ? [Object.assign(document.createElement("p"), { className: "nota", textContent: o.notaReferencia ?? `Linha tracejada: ${o.referencia.rotulo}. Acima dela, o candidato rendeu mais votos por real que a mediana.` })] : []),
    tabelaAlternativa(o.titulo, ["Candidato", Grandeza.split(" ")[0] ?? "Valor", eixoY?.coluna ?? "Votos", "Observação"], dados.map((d) => [d.rotulo, fmtX(d.custo), fmtY(valorY(d)), d.custo <= 0 || valorY(d) <= 0 ? "valor zero fora da escala log" : ""])),
  );
}

export function render(container: HTMLElement, dados: readonly PontoCustoVoto[], opcoes: OpcoesDispersao): GraficoDispersao {
  let atual: OpcoesDispersao = opcoes;
  desenhar(container, dados, atual);
  return {
    atualizar: (n) => { desenhar(container, n, atual); },
    destacar: (ids) => { atual = { ...atual, destaque: ids }; aplicarDestaque(container, ids); },
    destruir: () => {
      // Sair da tela com o tooltip fixo deixaria o balão no body e travaria o hover das demais telas.
      if (fixo !== null && container.contains(fixo)) soltar();
      container.replaceChildren();
    },
  };
}
