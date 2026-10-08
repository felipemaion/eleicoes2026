/**
 * Componente único de tooltip: fundo sólido, seta, posicionamento que não sai da tela.
 * Duas formas de uso, mesmo visual e mesma regra de posição:
 *  - `ligarPainel`: gatilho (botão "?") + painel já no DOM; abre por hover/foco/toque, fecha com Esc.
 *  - `criarFlutuante`: um balão compartilhado para marcas de gráficos/mapa (conteúdo trocado a cada hover).
 */
import { figuraCandidato } from "./foto-candidato";
import { posicionar, type Ancora } from "./posicionamento";

export interface ConteudoRico {
  titulo: string;
  linhas: readonly (readonly [rotulo: string, valor: string])[];
  /** Foto do candidato (`url: null` → placeholder com iniciais). */
  foto?: { nome: string; url: string | null };
  /** Linhas finais, fora da lista (ex.: "Clique para abrir no TSE"). */
  rodape?: readonly string[];
}

/** Monta o corpo padrão (título + lista de definição) de um tooltip. */
export function corpoRico(c: ConteudoRico): DocumentFragment {
  const f = document.createDocumentFragment();
  const t = document.createElement("strong");
  t.className = "tooltip-titulo";
  t.textContent = c.titulo;
  if (c.foto) {
    // Foto à esquerda do título, em cabeçalho próprio: a lista de valores ocupa a largura toda (sem float).
    const cab = document.createElement("div");
    cab.className = "tooltip-cabeca";
    cab.append(figuraCandidato(c.foto.nome, c.foto.url, 80, 100, "eager"), t);
    f.append(cab);
  } else f.append(t);
  const dl = document.createElement("dl");
  dl.className = "tooltip-lista tooltip-lista--dados";
  for (const [r, v] of c.linhas) {
    const dt = document.createElement("dt");
    dt.textContent = r;
    const dd = document.createElement("dd");
    dd.textContent = v;
    dl.append(dt, dd);
  }
  f.append(dl);
  for (const linha of c.rodape ?? []) {
    const p = document.createElement("p");
    p.className = "tooltip-rodape";
    p.textContent = linha;
    f.append(p);
  }
  return f;
}

const viewport = (): { largura: number; altura: number } => ({ largura: document.documentElement.clientWidth, altura: window.innerHeight });

/** Aplica a posição calculada a um elemento `position: fixed`. O elemento precisa estar visível para ser medido. */
export function encaixar(caixa: HTMLElement, ancora: Ancora): void {
  caixa.classList.add("tooltip");
  caixa.style.maxWidth = "";
  caixa.style.left = "0px";
  caixa.style.top = "0px";
  const r = caixa.getBoundingClientRect();
  const p = posicionar(ancora, { largura: r.width, altura: r.height }, viewport());
  caixa.style.maxWidth = `${String(p.largura)}px`;
  caixa.style.left = `${String(Math.round(p.x))}px`;
  caixa.style.top = `${String(Math.round(p.y))}px`;
  caixa.dataset["lado"] = p.lado;
  caixa.style.setProperty("--seta", `${String(Math.round(p.seta))}px`);
}

const ancoraDe = (el: Element): Ancora => {
  const r = el.getBoundingClientRect();
  return { x: r.left, y: r.top, largura: r.width, altura: r.height };
};

/**
 * Liga um painel (já no DOM, irmão do gatilho) ao gatilho.
 * Hover/foco abrem; clique/toque fixa (e um segundo clique fecha); Esc fecha e devolve o foco.
 */
export function ligarPainel(raiz: HTMLElement, gatilho: HTMLElement, painel: HTMLElement): void {
  let fixo = false;
  let devolvendoFoco = false;
  const abrir = (): void => {
    painel.hidden = false;
    gatilho.setAttribute("aria-expanded", "true");
    encaixar(painel, ancoraDe(gatilho));
  };
  const fechar = (): void => {
    fixo = false;
    painel.hidden = true;
    gatilho.setAttribute("aria-expanded", "false");
  };
  painel.classList.add("tooltip");
  gatilho.addEventListener("click", () => {
    if (!painel.hidden && fixo) fechar();
    else { fixo = true; abrir(); }
  });
  gatilho.addEventListener("mouseenter", () => { if (painel.hidden) abrir(); });
  raiz.addEventListener("mouseleave", () => { if (!fixo) fechar(); });
  gatilho.addEventListener("focus", () => { if (painel.hidden && !devolvendoFoco) abrir(); });
  raiz.addEventListener("focusout", (e) => {
    const para = e.relatedTarget;
    if (!fixo && !(para instanceof Node && raiz.contains(para))) fechar();
  });
  raiz.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || painel.hidden) return;
    e.stopPropagation();
    fechar();
    // Devolver o foco dispararia o "abrir por foco" logo em seguida.
    devolvendoFoco = true;
    gatilho.focus();
    devolvendoFoco = false;
  });
  // WCAG 1.4.13: Esc dispensa o balão mesmo quando só o ponteiro (sem foco) o abriu.
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !painel.hidden) fechar(); });
  // Clique fora fecha o painel fixado (toque).
  document.addEventListener("pointerdown", (e) => {
    if (!painel.hidden && fixo && e.target instanceof Node && !raiz.contains(e.target)) fechar();
  });
  const reposicionar = (): void => { if (!painel.hidden) encaixar(painel, ancoraDe(gatilho)); };
  window.addEventListener("resize", reposicionar);
  window.addEventListener("scroll", reposicionar, { passive: true, capture: true });
}

export interface Flutuante {
  /** Mostra `conteudo` junto da âncora (coordenadas de viewport). */
  mostrar(conteudo: Node, ancora: Ancora): void;
  /** Reposiciona o balão aberto sem trocar o conteúdo (não recria a foto a cada movimento do cursor). */
  mover(ancora: Ancora): void;
  esconder(): void;
  readonly elemento: HTMLElement;
}

let contador = 0;

/** Balão compartilhado (um por tela/gráfico); fecha com Esc em qualquer lugar. */
export function criarFlutuante(pai: HTMLElement = document.body): Flutuante {
  const el = document.createElement("div");
  el.className = "tooltip tooltip-flutuante";
  el.id = `tooltip-${String(++contador)}`;
  el.setAttribute("role", "tooltip");
  el.hidden = true;
  pai.append(el);
  const esconder = (): void => { el.hidden = true; };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") esconder(); });
  return {
    elemento: el,
    mostrar(conteudo, ancora) {
      el.replaceChildren(conteudo);
      el.hidden = false;
      encaixar(el, ancora);
    },
    mover(ancora) { if (!el.hidden) encaixar(el, ancora); },
    esconder,
  };
}

/** Âncora pontual (cursor) para `mostrar`. */
export const ancoraEm = (x: number, y: number): Ancora => ({ x, y, largura: 0, altura: 0 });

/** Liga hover/foco de uma marca (SVG ou HTML) a um balão com o `conteudo`. */
export function ligarMarca(marca: Element, flutuante: Flutuante, conteudo: () => Node): void {
  marca.addEventListener("mouseenter", (e) => { flutuante.mostrar(conteudo(), ancoraEm((e as MouseEvent).clientX, (e as MouseEvent).clientY)); });
  marca.addEventListener("mousemove", (e) => { flutuante.mover(ancoraEm((e as MouseEvent).clientX, (e as MouseEvent).clientY)); });
  marca.addEventListener("mouseleave", () => { flutuante.esconder(); });
  marca.addEventListener("focus", () => { flutuante.mostrar(conteudo(), ancoraDe(marca)); });
  marca.addEventListener("blur", () => { flutuante.esconder(); });
}
