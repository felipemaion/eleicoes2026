import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { criarCartao, type OpcoesCartao } from "../../src/telas/comparador-cartao";
import type { ClienteApi } from "../../src/dados/cliente";
import type { Lado } from "../../src/dados/comparador-logica";
import type { CandidaturaBusca } from "../../src/dados/contrato";
import busca from "../fixtures/api/busca.json";

const base = busca.itens[0] as unknown as CandidaturaBusca;
const candidaturas = (n: number): CandidaturaBusca[] => Array.from({ length: n }, (_, i) => ({ ...base, ano: 2022, sq_candidato: 100 + i, nm_urna: `GUTO ${String(i)}`, uf: "SP", votos: 1000 - i }));
const GRUPOS = [{ id: "mbl_2022", rotulo: "MBL 2022", ano: 2022 }, { id: "mbl_2022_indicados", rotulo: "MBL 2022 — indicados", ano: 2022 }];

beforeEach(() => { vi.useFakeTimers(); document.body.innerHTML = '<div id="x"></div>'; });
afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ""; });

function montar(lado: Lado, extra: Partial<OpcoesCartao> = {}, itens = candidaturas(12)) {
  const buscar = vi.fn(() => Promise.resolve({ total: itens.length, limite: 40, itens, dt_geracao: "2026-10-07" }));
  const aplicar = vi.fn();
  const fim = criarCartao(document.getElementById("x") as HTMLElement, {
    ano: 2022, cliente: { busca: buscar } as unknown as ClienteApi, grupos: GRUPOS, lado, nome: "MBL 2022", nomes: new Map(), indicados: new Set<string>(),
    cargo: "DEPUTADO ESTADUAL", uf: "SP", aplicar, ...extra,
  });
  return { buscar, aplicar, fim };
}
// O tipo do elemento é só para quem chama; não há outro uso para o parâmetro.
// eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
const q = <E extends HTMLElement = HTMLElement>(s: string): E => document.querySelector(s) as E;
const digitar = async (v: string): Promise<void> => {
  const input = q<HTMLInputElement>("input[role=combobox]");
  input.value = v;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await vi.advanceTimersByTimeAsync(300);
};

describe("cartão de um lado", () => {
  it("mostra o ano, o que está escolhido em uma linha e o botão Alterar; o editor começa fechado", () => {
    montar({ tipo: "grupo", id: "mbl_2022" });
    expect(q("h2").textContent).toBe("2022");
    expect(q(".cartao-resumo").textContent).toBe("MBL 2022");
    const alterar = q<HTMLButtonElement>("button[data-acao=alterar]");
    expect(alterar.getAttribute("aria-expanded")).toBe("false");
    expect(q(".cartao-editor").hidden).toBe(true);
  });

  it("Alterar → grupo: o select tem só os grupos do ano e Aplicar devolve o grupo", () => {
    const { aplicar } = montar({ tipo: "grupo", id: "mbl_2022" });
    q<HTMLButtonElement>("button[data-acao=alterar]").click();
    expect(q(".cartao-editor").hidden).toBe(false);
    const sel = q<HTMLSelectElement>("select[name=grupo]");
    expect([...sel.options].map((o) => o.value)).toEqual(["mbl_2022", "mbl_2022_indicados"]);
    sel.value = "mbl_2022_indicados";
    sel.dispatchEvent(new Event("change"));
    q<HTMLButtonElement>("button[data-acao=aplicar]").click();
    expect(aplicar).toHaveBeenCalledWith({ tipo: "grupo", id: "mbl_2022_indicados" });
  });

  it("candidatos: busca com ano, cargo e UF do recorte, no máximo 8 sugestões, chip ao escolher", async () => {
    const { buscar, aplicar } = montar({ tipo: "grupo", id: "mbl_2022" });
    q<HTMLButtonElement>("button[data-acao=alterar]").click();
    q<HTMLInputElement>("input[value=candidatos]").click();
    expect(q<HTMLButtonElement>("button[data-acao=aplicar]").disabled).toBe(true);
    await digitar("guto");
    expect(buscar).toHaveBeenCalledTimes(1);
    const pedido = (buscar.mock.calls[0] as unknown as [Record<string, string>])[0];
    expect(pedido).toMatchObject({ q: "guto", ano: "2022", cargo: "DEPUTADO ESTADUAL", uf: "SP" });
    expect(document.querySelectorAll("[role=option]")).toHaveLength(8);
    (document.querySelectorAll("[role=option]")[1] as HTMLElement).dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    expect(document.querySelectorAll(".chip-candidato")).toHaveLength(1);
    expect(q(".chip-candidato").textContent).toContain("GUTO 1");
    expect(q<HTMLInputElement>("input[role=combobox]").value).toBe("");
    q<HTMLButtonElement>("button[data-acao=aplicar]").click();
    expect(aplicar).toHaveBeenCalledWith({ tipo: "candidatos", sqs: ["101"] });
  });

  it("quem já virou chip não volta nas sugestões; o chip se remove pelo botão com nome acessível", async () => {
    montar({ tipo: "candidatos", sqs: ["100"] }, { nomes: new Map([["100", "GUTO 0"]]) });
    q<HTMLButtonElement>("button[data-acao=alterar]").click();
    expect(q(".chip-candidato").textContent).toContain("GUTO 0");
    await digitar("guto");
    expect(document.querySelectorAll("[role=option]")).toHaveLength(8);
    expect([...document.querySelectorAll("[role=option]")].some((o) => o.textContent.includes("GUTO 0"))).toBe(false);
    q<HTMLButtonElement>("button[aria-label='Remover GUTO 0']").click();
    expect(document.querySelectorAll(".chip-candidato")).toHaveLength(0);
    expect(q<HTMLButtonElement>("button[data-acao=aplicar]").disabled).toBe(true);
  });

  it("indicados: selo nas sugestões e nos chips; o grupo de indicados é explicado com os quatro nomes", async () => {
    const itens = candidaturas(3).map((c, i) => ({ ...c, indicado: i === 0 }));
    montar({ tipo: "grupo", id: "mbl_2022_indicados" }, {}, itens);
    q<HTMLButtonElement>("button[data-acao=alterar]").click();
    expect(q(".cartao-painel .nota").textContent).toMatch(/Kim Kataguiri.*Guto Zacarias.*Renato Battista.*Cristiano Beraldo/);
    q<HTMLInputElement>("input[value=candidatos]").click();
    await digitar("guto");
    const ops = [...document.querySelectorAll("[role=option]")];
    expect(ops.filter((o) => o.querySelector(".selo"))).toHaveLength(1);
    (ops.find((o) => o.querySelector(".selo")) as HTMLElement).dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    expect(q(".chip-candidato .selo").textContent).toBe("indicado MBL");
  });

  it("Cancelar descarta o rascunho e fecha; erro do lado aparece no cartão", () => {
    const { aplicar } = montar({ tipo: "grupo", id: "mbl_2022" }, { erro: "Nenhum candidato neste cargo." });
    expect(q("[role=alert]").textContent).toBe("Nenhum candidato neste cargo.");
    q<HTMLButtonElement>("button[data-acao=alterar]").click();
    q<HTMLButtonElement>("button[data-acao=cancelar]").click();
    expect(q(".cartao-editor").hidden).toBe(true);
    expect(aplicar).not.toHaveBeenCalled();
  });
});
