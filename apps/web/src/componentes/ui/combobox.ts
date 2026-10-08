/**
 * Combobox (padrão ARIA 1.2 "list autocomplete"): o foco fica no campo; a opção ativa é
 * anunciada por `aria-activedescendant`. Núcleo compartilhado pela busca global e pelo seletor de UF.
 */
export interface ItemCombobox {
  id: string;
  /** Preenche o `<li>` da opção (permite destaque de trecho, subtítulo etc.). */
  desenhar(li: HTMLElement): void;
}

export type ModoEscolha = "principal" | "alternativo";

export interface OpcoesCombobox {
  rotuloLista: string;
  /** `alternativo` = Shift/Ctrl+Enter (ex.: "ver no mapa" em vez de "abrir a ficha"). */
  aoEscolher(item: ItemCombobox, modo: ModoEscolha): void;
}

export interface Combobox {
  definirItens(itens: readonly ItemCombobox[]): void;
  abrir(): void;
  fechar(): void;
  readonly aberto: boolean;
  destruir(): void;
}

/** Próximo índice ativo com volta nas pontas; -1 quando não há itens. */
export function proximoIndice(atual: number, tecla: "ArrowDown" | "ArrowUp", n: number): number {
  if (n <= 0) return -1;
  if (tecla === "ArrowDown") return atual >= n - 1 ? 0 : atual + 1;
  return atual <= 0 ? n - 1 : atual - 1;
}

let seq = 0;

export function criarCombobox(input: HTMLInputElement, opcoes: OpcoesCombobox): Combobox {
  const base = `cb-${String(++seq)}`;
  const lista = document.createElement("ul");
  lista.id = `${base}-lista`;
  lista.className = "combobox-lista";
  lista.setAttribute("role", "listbox");
  lista.setAttribute("aria-label", opcoes.rotuloLista);
  lista.hidden = true;
  input.after(lista);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", lista.id);
  input.autocomplete = "off";

  let itens: readonly ItemCombobox[] = [];
  let ativo = -1;
  let aberto = false;

  const lis = (): HTMLElement[] => [...lista.querySelectorAll<HTMLElement>("[role=option]")];

  // scrollIntoView pode faltar (jsdom): por isso o cast parcial em `marcar`.
  function marcar(i: number): void {
    ativo = i;
    lis().forEach((li, k) => {
      if (k === i) { li.setAttribute("aria-selected", "true"); (li as Partial<HTMLElement>).scrollIntoView?.({ block: "nearest" }); } else li.removeAttribute("aria-selected");
    });
    if (i >= 0) input.setAttribute("aria-activedescendant", `${base}-op-${String(i)}`);
    else input.removeAttribute("aria-activedescendant");
  }

  function abrir(): void {
    if (itens.length === 0) return;
    aberto = true;
    lista.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function fechar(): void {
    aberto = false;
    lista.hidden = true;
    input.setAttribute("aria-expanded", "false");
    marcar(-1);
  }

  function escolher(i: number, modo: ModoEscolha): void {
    const item = itens[i];
    if (!item) return;
    fechar();
    opcoes.aoEscolher(item, modo);
  }

  function aoTeclar(e: KeyboardEvent): void {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (itens.length === 0) return;
      e.preventDefault();
      if (!aberto) abrir();
      marcar(proximoIndice(ativo, e.key, itens.length));
    } else if (e.key === "Enter") {
      if (!aberto) return;
      // Sem opção ativa, Enter escolhe a primeira: quem digitou e confirmou quer o melhor resultado.
      e.preventDefault();
      escolher(ativo >= 0 ? ativo : 0, e.shiftKey || e.ctrlKey || e.metaKey ? "alternativo" : "principal");
    } else if (e.key === "Escape" && aberto) {
      e.preventDefault();
      e.stopPropagation();
      fechar();
    }
  }
  const aoPerderFoco = (): void => { fechar(); };
  input.addEventListener("keydown", aoTeclar);
  input.addEventListener("blur", aoPerderFoco);

  return {
    definirItens(novos) {
      itens = novos;
      marcar(-1);
      lista.replaceChildren(...novos.map((item, i) => {
        const li = document.createElement("li");
        li.id = `${base}-op-${String(i)}`;
        li.setAttribute("role", "option");
        li.className = "combobox-opcao";
        item.desenhar(li);
        // mousedown (não click): dispara antes do blur do campo, que fecharia a lista antes do clique.
        li.addEventListener("mousedown", (ev) => { ev.preventDefault(); escolher(i, ev.shiftKey || ev.ctrlKey || ev.metaKey ? "alternativo" : "principal"); });
        return li;
      }));
      if (novos.length === 0) fechar();
    },
    abrir,
    fechar,
    get aberto() { return aberto; },
    destruir() {
      input.removeEventListener("keydown", aoTeclar);
      input.removeEventListener("blur", aoPerderFoco);
      for (const a of ["role", "aria-autocomplete", "aria-expanded", "aria-controls", "aria-activedescendant"]) input.removeAttribute(a);
      lista.remove();
    },
  };
}
