/** Helpers mínimos de DOM para as telas (sem framework de UI). */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Partial<HTMLElementTagNameMap[K]> = {},
  ...filhos: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...filhos);
  return e;
}

export interface OpcaoSelect {
  valor: string;
  texto: string;
  desabilitada?: boolean;
}

export interface CampoSelect {
  rotulo: HTMLLabelElement;
  select: HTMLSelectElement;
}

export function campoSelect(rotulo: string, nome: string, opcoes: readonly OpcaoSelect[], valor: string, aoMudar: (v: string) => void): CampoSelect {
  const select = h("select", { name: nome });
  for (const o of opcoes) {
    const op = new Option(o.texto, o.valor);
    op.disabled = o.desabilitada ?? false;
    select.add(op);
  }
  select.value = valor;
  select.addEventListener("change", () => { aoMudar(select.value); });
  return { rotulo: h("label", {}, rotulo, select), select };
}

export function titulo(texto: string): HTMLHeadingElement {
  return h("h1", { textContent: texto, tabIndex: -1 });
}

/** Rodapé de cada gráfico: unidade/denominador/fonte numa linha, sempre visível. */
export function nota(texto: string): HTMLParagraphElement {
  return h("p", { className: "nota", textContent: texto });
}
