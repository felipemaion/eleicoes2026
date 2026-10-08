import { axisBottom, scaleBand, scaleLinear, select } from "d3";
import { formatarCompacto, formatarMoeda } from "../../formato";
import { COR, criarSvg, marcaAcessivel, mensagemVazia, no, tabelaAlternativa, textoSvg, type Grafico, substituir } from "./base";

export interface ReceitaPorFonte {
  rotulo: string;
  valores: Readonly<Record<string, number>>;
}

export interface OpcoesEmpilhado {
  titulo: string;
  /** Fontes em ordem fixa: a cor de cada uma não depende da ordem nem do conteúdo dos dados.
   *  Sem esta opção, ordem alfabética. O que passar de 6 fontes (ou não estiver na lista) vira "Outras". */
  fontes?: readonly string[];
  largura?: number;
}

const ESQ = 150;
const DIR = 20;
const TOPO = 8;
const BAIXO = 28;
const LINHA = 28;

const OUTRAS = "Outras";

/** Reagrupa valores nas fontes visíveis; excedente soma em "Outras". Negativos (estornos) não entram. */
function agrupar(dados: readonly ReceitaPorFonte[], o: OpcoesEmpilhado): { fontes: string[]; linhas: ReceitaPorFonte[] } {
  const todas = o.fontes ?? [...new Set(dados.flatMap((d) => Object.keys(d.valores)))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const max = COR.serie.length;
  const visiveis = todas.length > max ? todas.slice(0, max - 1) : [...todas];
  const aparecemOutras = dados.some((d) => Object.entries(d.valores).some(([f, v]) => !visiveis.includes(f) && v > 0));
  const fontes = aparecemOutras ? [...visiveis, OUTRAS] : visiveis;
  const linhas = dados.map((d) => {
    const valores: Record<string, number> = {};
    for (const [f, v] of Object.entries(d.valores)) {
      const chave = visiveis.includes(f) ? f : OUTRAS;
      valores[chave] = (valores[chave] ?? 0) + Math.max(0, v);
    }
    return { rotulo: d.rotulo, valores };
  });
  return { fontes, linhas };
}

function desenhar(container: HTMLElement, brutos: readonly ReceitaPorFonte[], o: OpcoesEmpilhado): void {
  if (brutos.length === 0) { mensagemVazia(container); return; }
  const { fontes, linhas: dados } = agrupar(brutos, o);
  const w = o.largura ?? 640;
  const h = TOPO + BAIXO + dados.length * LINHA;
  const total = (d: ReceitaPorFonte): number => Object.values(d.valores).reduce((a, b) => a + b, 0);
  const x = scaleLinear().domain([0, Math.max(1, ...dados.map(total))]).nice().range([ESQ, w - DIR]);
  const y = scaleBand<number>().domain(dados.map((_, i) => i)).range([TOPO, h - BAIXO]).padding(0.25);

  const svg = criarSvg(w, h, `${o.titulo}. Barras empilhadas de receita por fonte (${fontes.join(", ")}) para ${String(dados.length)} candidatos.`);
  const eixo = select(svg).append("g").attr("class", "eixo-x").attr("transform", `translate(0,${String(h - BAIXO)})`);
  eixo.call(axisBottom(x).ticks(5).tickFormat((v) => formatarCompacto(+v)));
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

  substituir(container,
    svg,
    legenda,
    tabelaAlternativa(o.titulo, ["Candidato", ...fontes, "Total"], dados.map((d) => [d.rotulo, ...fontes.map((f) => formatarMoeda(d.valores[f] ?? 0)), formatarMoeda(total(d))])),
  );
}

export function render(container: HTMLElement, dados: readonly ReceitaPorFonte[], opcoes: OpcoesEmpilhado): Grafico<readonly ReceitaPorFonte[]> {
  desenhar(container, dados, opcoes);
  return { atualizar: (n) => { desenhar(container, n, opcoes); }, destruir: () => { container.replaceChildren(); } };
}
