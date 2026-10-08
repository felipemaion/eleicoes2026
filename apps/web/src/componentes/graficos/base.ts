/** Peças comuns dos gráficos: SVG acessível, tabela alternativa e estado vazio. */
import { PALETAS } from "../../paletas";

export const SVG_NS = "http://www.w3.org/2000/svg";

/** Contrato comum: todo gráfico devolve este handle de `render`. */
export interface Grafico<D> {
  atualizar(dados: D): void;
  destruir(): void;
}

export function no<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number> = {},
  texto?: string,
): SVGElementTagNameMap[K] {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (texto !== undefined) e.textContent = texto;
  return e;
}

/** Cores dos gráficos: só das paletas centrais (ver `paletas.ts`). */
export const COR = {
  /** Marcas de dados: token do tema (amarelo no escuro, âmbar no claro). */
  principal: "var(--cor-dado)",
  antes: PALETAS.categorica[1],
  depois: PALETAS.categorica[5],
  zero: PALETAS.categorica[6],
  /** Okabe-Ito sem o preto (índice 0), que some no tema escuro. */
  serie: PALETAS.categorica.slice(1),
} as const;

export interface Margens {
  topo: number;
  direita: number;
  baixo: number;
  esquerda: number;
}

export function criarSvg(largura: number, altura: number, rotulo: string): SVGSVGElement {
  const svg = no("svg", {
    viewBox: `0 0 ${String(largura)} ${String(altura)}`,
    width: "100%",
    // "group", não "img": img torna os filhos apresentacionais e esconde as marcas focáveis.
    role: "group",
    "aria-label": rotulo,
    class: "grafico",
  });
  return svg;
}

/** Torna uma marca focável e descrita pelo `aria-label`. Sem `<title>`: o tooltip nativo apareceria por cima do tooltip rico. */
export function marcaAcessivel(m: SVGElement, rotulo: string): void {
  m.setAttribute("role", "img");
  m.setAttribute("tabindex", "0");
  m.setAttribute("aria-label", rotulo);
}

export function mensagemVazia(container: HTMLElement): void {
  const p = document.createElement("p");
  p.className = "grafico-vazio";
  p.textContent = "Sem dados para exibir.";
  container.replaceChildren(p);
}

/** `<details>` com `<table>`: alternativa textual a cada gráfico (WCAG 1.1.1). */
export function tabelaAlternativa(titulo: string, colunas: readonly string[], linhas: readonly (readonly string[])[]): HTMLDetailsElement {
  const d = document.createElement("details");
  d.className = "grafico-tabela";
  const s = document.createElement("summary");
  s.textContent = "Ver dados em tabela";
  const t = document.createElement("table");
  const cap = t.createCaption();
  cap.textContent = titulo;
  const tr = t.createTHead().insertRow();
  for (const c of colunas) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = c;
    tr.append(th);
  }
  const corpo = t.createTBody();
  for (const l of linhas) {
    const r = corpo.insertRow();
    l.forEach((v, i) => {
      const cel = i === 0 ? document.createElement("th") : document.createElement("td");
      if (i === 0) (cel).scope = "row";
      cel.textContent = v;
      r.append(cel);
    });
  }
  d.append(s, t);
  return d;
}

/** Estilo de texto herdando o tema via variáveis CSS. */
export function textoSvg(x: number, y: number, texto: string, extra: Record<string, string | number> = {}): SVGTextElement {
  return no("text", { x, y, fill: "var(--cor-texto)", "font-size": 12, ...extra }, texto);
}

/**
 * Troca o conteúdo do contêiner preservando o que o usuário já fez: `<details>` aberto
 * continua aberto e o foco volta à mesma marca/resumo (senão `atualizar` joga o leitor de tela
 * e quem navega por teclado de volta ao início).
 */
export function substituir(container: HTMLElement, ...novos: Node[]): void {
  const abertos = [...container.querySelectorAll("details")].map((d) => d.open);
  const ativo = document.activeElement;
  let foco: { tipo: "marca" | "resumo"; indice: number } | null = null;
  if (ativo && container.contains(ativo)) {
    const marcas = [...container.querySelectorAll(".marca")];
    const resumos = [...container.querySelectorAll("summary")];
    if (marcas.includes(ativo)) foco = { tipo: "marca", indice: marcas.indexOf(ativo) };
    else if (resumos.includes(ativo as HTMLElement)) foco = { tipo: "resumo", indice: resumos.indexOf(ativo as HTMLElement) };
  }
  container.replaceChildren(...novos);
  container.querySelectorAll("details").forEach((d, i) => { if (abertos[i]) d.open = true; });
  if (foco) {
    const alvo = container.querySelectorAll(foco.tipo === "marca" ? ".marca" : "summary")[foco.indice];
    if (alvo instanceof HTMLElement || alvo instanceof SVGElement) alvo.focus();
  }
}
