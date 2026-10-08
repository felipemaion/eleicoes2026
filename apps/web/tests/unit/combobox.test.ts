import { afterEach, describe, expect, it, vi } from "vitest";
import { criarCombobox, proximoIndice } from "../../src/componentes/ui/combobox";

describe("proximoIndice", () => {
  it("anda com as setas e dá a volta nas pontas; sem itens fica em -1", () => {
    expect(proximoIndice(-1, "ArrowDown", 3)).toBe(0);
    expect(proximoIndice(2, "ArrowDown", 3)).toBe(0);
    expect(proximoIndice(-1, "ArrowUp", 3)).toBe(2);
    expect(proximoIndice(0, "ArrowUp", 3)).toBe(2);
    expect(proximoIndice(0, "ArrowDown", 0)).toBe(-1);
  });
});

function montar() {
  document.body.innerHTML = '<label for="c">Buscar</label><input id="c" />';
  const input = document.querySelector<HTMLInputElement>("#c") as HTMLInputElement;
  const escolhidos: string[] = [];
  const cb = criarCombobox(input, {
    rotuloLista: "Sugestões",
    aoEscolher: (item, modo) => { escolhidos.push(`${item.id}:${modo}`); },
  });
  cb.definirItens([
    { id: "a", desenhar: (li) => { li.textContent = "Alfa"; } },
    { id: "b", desenhar: (li) => { li.textContent = "Beta"; } },
  ]);
  return { input, cb, escolhidos };
}
afterEach(() => { document.body.innerHTML = ""; });
const tecla = (el: HTMLElement, key: string, extra: KeyboardEventInit = {}): void => { el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...extra })); };

describe("combobox acessível", () => {
  it("papéis ARIA: combobox, listbox e opções ligadas ao campo", () => {
    const { input } = montar();
    expect(input.getAttribute("role")).toBe("combobox");
    expect(input.getAttribute("aria-autocomplete")).toBe("list");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    const lista = document.getElementById(input.getAttribute("aria-controls") ?? "") as HTMLElement;
    expect(lista.getAttribute("role")).toBe("listbox");
    expect(lista.getAttribute("aria-label")).toBe("Sugestões");
    expect(lista.querySelectorAll("[role=option]")).toHaveLength(2);
  });
  it("seta abre, move a opção ativa (aria-activedescendant) e Enter escolhe", () => {
    const { input, escolhidos } = montar();
    tecla(input, "ArrowDown");
    expect(input.getAttribute("aria-expanded")).toBe("true");
    const ativa = input.getAttribute("aria-activedescendant") ?? "";
    expect(document.getElementById(ativa)?.textContent).toBe("Alfa");
    tecla(input, "ArrowDown");
    tecla(input, "Enter");
    expect(escolhidos).toEqual(["b:principal"]);
    expect(input.getAttribute("aria-expanded")).toBe("false");
  });
  it("Shift+Enter escolhe pelo modo alternativo", () => {
    const { input, escolhidos } = montar();
    tecla(input, "ArrowDown");
    tecla(input, "Enter", { shiftKey: true });
    expect(escolhidos).toEqual(["a:alternativo"]);
  });
  it("Esc fecha sem escolher; clique com o mouse escolhe", () => {
    const { input, escolhidos } = montar();
    tecla(input, "ArrowDown");
    tecla(input, "Escape");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    expect(escolhidos).toEqual([]);
    tecla(input, "ArrowDown");
    (document.querySelectorAll("[role=option]")[1] as HTMLElement).dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    expect(escolhidos).toEqual(["b:principal"]);
  });
  it("sem itens, a lista fica fechada; destruir limpa os atributos", () => {
    const { input, cb } = montar();
    cb.definirItens([]);
    tecla(input, "ArrowDown");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    const fn = vi.fn();
    cb.destruir();
    input.addEventListener("keydown", fn);
    expect(input.hasAttribute("role")).toBe(false);
  });
});
