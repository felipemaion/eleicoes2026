import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "../../src/componentes/filtros/filtros";
import type { ClienteApi } from "../../src/dados/cliente";
import { criarStore } from "../../src/store";

beforeEach(() => { vi.useFakeTimers(); document.body.innerHTML = '<div id="x"></div>'; });
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ""; });

function montar(total = 547) {
  const candidatos = vi.fn(() => Promise.resolve({ total, limite: 1, offset: 0, itens: [], kpis: null }));
  const store = criarStore();
  const fim = render(document.getElementById("x") as HTMLElement, store, { candidatos } as unknown as ClienteApi);
  return { store, candidatos, fim };
}
const radio = (grupo: string, texto: string): HTMLInputElement => {
  const r = [...document.querySelectorAll<HTMLInputElement>(`input[type=radio][name=${grupo}]`)].find((i) => i.labels?.[0]?.textContent === texto);
  if (!r) throw new Error(`sem rádio ${grupo}/${texto}`);
  return r;
};
const uf = (): HTMLInputElement => document.querySelector<HTMLInputElement>("input[name=uf]") as HTMLInputElement;

describe("filtros", () => {
  it("ano e cargo são segmentos (rádios) refletindo o store; clicar muda o estado sem recarregar", () => {
    const { store } = montar();
    expect(radio("ano", "2026").checked).toBe(true);
    expect(radio("cargo", "Deputado federal").checked).toBe(true);
    radio("ano", "2022").click();
    radio("cargo", "Senador").click();
    expect(store.obter().filtros).toMatchObject({ ano: 2022, cargo: "senador" });
    expect(radio("ano", "2022").checked).toBe(true);
  });
  it("presidente leva a Brasil e trava a UF, explicando o motivo", () => {
    const { store } = montar();
    store.definir({ uf: "SP" });
    radio("cargo", "Presidente").click();
    expect(store.obter().filtros.uf).toBe("BR");
    expect(uf().disabled).toBe(true);
    expect(document.querySelector(".filtros")?.textContent).toMatch(/eleição nacional/i);
    radio("cargo", "Senador").click();
    expect(uf().disabled).toBe(false);
  });
  it("UF: digita para filtrar, Enter escolhe", () => {
    const { store } = montar();
    uf().value = "sergi";
    uf().dispatchEvent(new Event("input", { bubbles: true }));
    uf().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    expect(store.obter().filtros.uf).toBe("SE");
    expect(uf().value).toBe("Sergipe (SE)");
  });
  it("grupo mostra descrição curta do escolhido", () => {
    const { store } = montar();
    const sel = document.querySelector<HTMLSelectElement>("select[name=grupo]") as HTMLSelectElement;
    expect(document.querySelector(".filtro-grupo-desc")?.textContent).toMatch(/Missão/);
    sel.value = "mbl_2022";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    expect(store.obter().filtros.grupo).toBe("mbl_2022");
    expect(document.querySelector(".filtro-grupo-desc")?.textContent).toMatch(/MBL/);
  });
  it("contagem ao vivo, com debounce, usando os filtros atuais", async () => {
    const { store, candidatos } = montar();
    await vi.advanceTimersByTimeAsync(400);
    expect(document.querySelector(".filtros-contagem")?.textContent).toBe("547 candidaturas");
    expect(candidatos).toHaveBeenLastCalledWith({ ano: "2026", grupo: "missao_2026", cargo: "DEPUTADO FEDERAL", limite: "1" }, expect.anything());
    store.definir({ cargo: "senador" });
    store.definir({ uf: "SE" });
    await vi.advanceTimersByTimeAsync(400);
    expect(candidatos).toHaveBeenCalledTimes(2);
    expect(candidatos).toHaveBeenLastCalledWith({ ano: "2026", grupo: "missao_2026", cargo: "SENADOR", uf: "SE", limite: "1" }, expect.anything());
  });
  it("zero resultados orienta; falha da contagem não derruba os filtros", async () => {
    montar(0);
    await vi.advanceTimersByTimeAsync(400);
    expect(document.querySelector(".filtros-contagem")?.textContent).toMatch(/Nenhuma candidatura/);
  });
  it("Limpar volta ao padrão e some quando já está no padrão", () => {
    const { store } = montar();
    const limpar = document.querySelector<HTMLButtonElement>("button.filtros-limpar") as HTMLButtonElement;
    expect(limpar.hidden).toBe(true);
    store.definir({ cargo: "senador", uf: "SE", ano: 2022, candidato: "2022:9" });
    expect(limpar.hidden).toBe(false);
    limpar.click();
    expect(store.obter().filtros).toMatchObject({ cargo: "deputado_federal", uf: "BR", ano: 2026, grupo: "missao_2026", candidato: "" });
  });
});
