import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "../../src/componentes/filtros/filtros";
import type { ClienteApi } from "../../src/dados/cliente";
import { criarStore } from "../../src/store";

beforeEach(() => { vi.useFakeTimers(); document.body.innerHTML = '<div id="x"></div>'; });
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ""; });

const GRUPOS_API = {
  dt_geracao: "2026-10-07", comparacoes: [],
  grupos: [
    { id: "missao_2026", rotulo: "Partido Missão 2026", ano: 2026, n_candidaturas: 3 },
    { id: "mbl_2026", rotulo: "MBL 2026 (Missão + aliados)", ano: 2026, n_candidaturas: 4 },
    { id: "mbl_2022", rotulo: "MBL 2022", ano: 2022, n_candidaturas: 3 },
    { id: "mbl_2022_indicados", rotulo: "MBL 2022 — indicados", ano: 2022, n_candidaturas: 1 },
  ],
};

function montar(total = 547, ufsDisponiveis: string[] = ["SE", "SP"]) {
  const candidatos = vi.fn(() => Promise.resolve({ total, limite: 1, offset: 0, itens: [], kpis: null }));
  const ufs = vi.fn(() => Promise.resolve({ dt_geracao: "2026-10-07", itens: ufsDisponiveis.map((u) => ({ uf: u, candidaturas: 1 })) }));
  const grupos = vi.fn(() => Promise.resolve(GRUPOS_API));
  const store = criarStore();
  const fim = render(document.getElementById("x") as HTMLElement, store, { candidatos, ufs, grupos } as unknown as ClienteApi);
  return { store, candidatos, ufs, grupos, fim };
}
const radio = (grupo: string, texto: string): HTMLInputElement => {
  const r = [...document.querySelectorAll<HTMLInputElement>(`input[type=radio][name=${grupo}]`)].find((i) => i.labels?.[0]?.textContent === texto);
  if (!r) throw new Error(`sem rádio ${grupo}/${texto}`);
  return r;
};
const uf = (): HTMLInputElement => document.querySelector<HTMLInputElement>("input[name=uf]") as HTMLInputElement;

describe("filtros dependentes (UFs com candidatura)", () => {
  it("pede /candidatos/ufs do recorte (grupo + cargo) e só oferece essas UFs", async () => {
    const { ufs } = montar(1, ["SE"]);
    await vi.advanceTimersByTimeAsync(0);
    expect(ufs).toHaveBeenCalledWith({ grupo: "missao_2026", cargo: "DEPUTADO FEDERAL" }, expect.anything());
    uf().dispatchEvent(new Event("focus"));
    const itens = [...document.querySelectorAll("[role=option]")].map((o) => o.textContent);
    expect(itens).toEqual(["Brasil", "Sergipe (SE)"]);
  });
  it("trocar o cargo refaz a consulta; UF sem candidatura volta para Brasil", async () => {
    const { store, ufs } = montar(1, ["SP"]);
    store.definir({ uf: "SE" });
    await vi.advanceTimersByTimeAsync(0);
    expect(store.obter().filtros.uf).toBe("BR");
    radio("cargo", "Senador").click();
    await vi.advanceTimersByTimeAsync(0);
    expect(ufs).toHaveBeenLastCalledWith({ grupo: "missao_2026", cargo: "SENADOR" }, expect.anything());
  });
  it("não consulta para presidente (UF travada em Brasil)", async () => {
    const { ufs, store } = montar();
    await vi.advanceTimersByTimeAsync(0);
    ufs.mockClear();
    store.definir({ cargo: "presidente" });
    await vi.advanceTimersByTimeAsync(0);
    expect(ufs).not.toHaveBeenCalled();
  });
});

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
  it("grupo: opções vêm da API (todos os grupos) e a descrição acompanha o escolhido", async () => {
    const { store } = montar();
    await vi.advanceTimersByTimeAsync(0);
    const sel = document.querySelector<HTMLSelectElement>("select[name=grupo]") as HTMLSelectElement;
    expect([...sel.options].map((o) => o.value)).toEqual(["missao_2026", "mbl_2026", "mbl_2022", "mbl_2022_indicados"]);
    expect(sel.value).toBe("missao_2026");
    expect(document.querySelector(".filtro-grupo-desc")?.textContent).toMatch(/Missão.*2026.*3 candidaturas/);
    sel.value = "mbl_2026";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    expect(store.obter().filtros.grupo).toBe("mbl_2026");
    expect(document.querySelector(".filtro-grupo-desc")?.textContent).toMatch(/aliados.*4 candidaturas/);
  });
  it("grupo da URL que a API não conhece continua visível no seletor (não some em silêncio)", async () => {
    const { store } = montar();
    store.definir({ grupo: "novo_grupo" });
    await vi.advanceTimersByTimeAsync(0);
    const sel = document.querySelector<HTMLSelectElement>("select[name=grupo]") as HTMLSelectElement;
    expect(sel.value).toBe("novo_grupo");
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

describe("filtros na tela Evolução (T-W22)", () => {
  const campoGrupo = (): HTMLElement => document.querySelector(".filtro-grupo") as HTMLElement;
  const contagem = (): HTMLElement => document.querySelector(".filtros-contagem") as HTMLElement;
  it("esconde o grupo comparado e a contagem (a escolha é nos cartões) e volta nas outras telas", async () => {
    const { store } = montar();
    await vi.advanceTimersByTimeAsync(300);
    expect(campoGrupo().hidden).toBe(false);
    expect(contagem().hidden).toBe(false);
    store.definir({}, "evolucao");
    expect(campoGrupo().hidden).toBe(true);
    expect(contagem().hidden).toBe(true);
    store.definir({}, "mapa");
    expect(campoGrupo().hidden).toBe(false);
    expect(contagem().hidden).toBe(false);
  });
});
