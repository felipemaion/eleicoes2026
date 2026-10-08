import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "../../src/componentes/busca/busca";
import type { ClienteApi } from "../../src/dados/cliente";
import { FILTROS_PADRAO } from "../../src/store";
import { listaTipada } from "../fixtures/api/tipado";
import busca from "../fixtures/api/busca.json";

const RESPOSTA = listaTipada(busca);
beforeEach(() => { vi.useFakeTimers(); document.body.innerHTML = '<div id="x"></div>'; });
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ""; });

function montar(buscar = vi.fn(() => Promise.resolve(RESPOSTA))) {
  const navegar = vi.fn();
  const fim = render(document.getElementById("x") as HTMLElement, { cliente: { busca: buscar } as unknown as ClienteApi, filtros: () => FILTROS_PADRAO, navegar });
  const input = document.querySelector<HTMLInputElement>("input[role=combobox]") as HTMLInputElement;
  return { buscar, navegar, input, fim };
}
const digitar = async (input: HTMLInputElement, v: string): Promise<void> => {
  input.value = v;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.advanceTimersByTimeAsync(300);
};

describe("busca global", () => {
  it("tem rótulo acessível e dica do atalho '/'", () => {
    const { input } = montar();
    expect(document.querySelector(`label[for=${input.id}]`)?.textContent).toMatch(/Buscar candidato/);
    expect(document.body.textContent).toMatch(/\//);
  });
  it("debounce: uma chamada só para várias teclas; menos de 2 caracteres não busca", async () => {
    const { input, buscar } = montar();
    await digitar(input, "k");
    expect(buscar).not.toHaveBeenCalled();
    input.value = "ki"; input.dispatchEvent(new Event("input"));
    input.value = "kim"; input.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(300);
    expect(buscar).toHaveBeenCalledTimes(1);
    expect(buscar).toHaveBeenCalledWith({ q: "kim", limite: "8" }, expect.anything());
  });
  it("sugestões mostram nome com trecho destacado e a linha de contexto", async () => {
    const { input } = montar();
    await digitar(input, "candidata");
    const op = document.querySelector("[role=option]") as HTMLElement;
    expect(op.querySelector("mark")?.textContent.toLowerCase()).toBe("candidata");
    expect(op.textContent).toContain("2026 · Deputado federal · SE · MISSÃO (14) · 12.345 votos");
  });
  it("Enter abre a ficha; Shift+Enter fixa no mapa", async () => {
    const { input, navegar } = montar();
    await digitar(input, "candidata");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    expect(navegar).toHaveBeenLastCalledWith("#/candidato?uf=SE&cand=2026%3A1");
    await digitar(input, "candidata");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, shiftKey: true }));
    expect(navegar).toHaveBeenLastCalledWith("#/mapa?uf=SE&cand=2026%3A1");
  });
  it("sem resultado e falha da busca têm mensagem própria (nunca erro genérico da página)", async () => {
    const vazio = montar(vi.fn(() => Promise.resolve({ ...RESPOSTA, total: 0, itens: [] })));
    await digitar(vazio.input, "zzzz");
    expect(document.querySelector(".busca-estado")?.textContent).toMatch(/Nenhum candidato/);
    vazio.fim();
    const erro = montar(vi.fn(() => Promise.reject(new Error("500"))));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await digitar(erro.input, "zzzz");
    expect(document.querySelector(".busca-estado")?.textContent).toMatch(/Busca indisponível/);
  });
  it("atalho '/' foca a busca, exceto ao digitar em outro campo", () => {
    const { input } = montar();
    document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
    expect(document.activeElement).toBe(input);
    input.blur();
    const outro = document.createElement("input");
    document.body.append(outro);
    outro.focus();
    outro.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true }));
    expect(document.activeElement).toBe(outro);
  });
});
