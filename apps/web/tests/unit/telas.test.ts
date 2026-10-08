import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import grupos from "../fixtures/api/grupos.json";
import mapa from "../fixtures/api/mapa.json";
import municipio from "../fixtures/api/municipio.json";
import { FILTROS_PADRAO, type Estado, type Tela as Chave } from "../../src/store";

const mapaFalso = vi.hoisted(() => {
  const instancias: { definirValores: ReturnType<typeof vi.fn>; destruir: ReturnType<typeof vi.fn>; definirPontos: ReturnType<typeof vi.fn> }[] = [];
  return { instancias };
});
vi.mock("../../src/telas/mapa-embutido", () => ({
  montarMapa: vi.fn(() => {
    const m = { definirValores: vi.fn(), definirPontos: vi.fn(), destruir: vi.fn(), pronto: Promise.resolve(), estatisticas: () => ({ fontesCarregadas: 1, atualizacoesDeValores: 0 }) };
    mapaFalso.instancias.push(m);
    return Promise.resolve(m);
  }),
}));

const ROTAS: Record<string, unknown> = {
  "/api/candidatos": candidatos, "/api/grupos": grupos, "/api/mapa": mapa, "/api/mapa/pontos": { pontos: [] },
  "/api/gastos": gastos, "/api/comparativo": comparativo, "/api/candidatos/2026/1": ficha, "/api/municipios/2800308": municipio,
};
let chamadas: string[];
function simularApi(sobrescrever: Record<string, unknown> = {}): void {
  chamadas = [];
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    chamadas.push(url);
    const caminho = url.split("?")[0] ?? url;
    const corpo = sobrescrever[caminho] ?? ROTAS[caminho];
    if (corpo === undefined || corpo instanceof Error) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(corpo) });
  }));
}

const estado = (tela: Chave, filtros: Partial<Estado["filtros"]> = {}): Estado => ({ tela, filtros: { ...FILTROS_PADRAO, ...filtros } });
let el: HTMLElement;
beforeEach(() => {
  document.body.innerHTML = '<main id="m"></main>';
  el = document.getElementById("m") as HTMLElement;
  mapaFalso.instancias.length = 0;
  simularApi();
});
afterEach(() => { vi.unstubAllGlobals(); });

async function desenhar(chave: Chave, e: Estado = estado(chave)): Promise<() => void> {
  const { TELAS_POR_CHAVE } = await import("../../src/telas");
  return TELAS_POR_CHAVE[chave].render(el, e);
}
const chamou = (trecho: string): boolean => chamadas.some((c) => c.includes(trecho));

describe("estados comuns", () => {
  it("mostra 'Carregando' (role=status) e depois o conteúdo; h1 sempre presente", async () => {
    await desenhar("visao-geral");
    expect(el.querySelector("h1")?.textContent).toBe("Visão geral");
    expect(el.querySelector("[role=status]")?.textContent).toMatch(/Carregando/);
    await vi.waitFor(() => { expect(el.querySelector("[role=status]")).toBeNull(); });
  });
  it("erro da API vira alerta com 'Tentar novamente' que refaz a busca", async () => {
    simularApi({ "/api/candidatos": new Error("x") });
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelector("[role=alert]")).not.toBeNull(); });
    expect(el.querySelector("[role=alert]")?.textContent).toMatch(/500/);
    simularApi();
    el.querySelector<HTMLButtonElement>("[role=alert] button")?.click();
    await vi.waitFor(() => { expect(el.querySelector("dl.kpis")).not.toBeNull(); });
  });
  it("lista vazia mostra mensagem de vazio, não gráfico em branco", async () => {
    simularApi({ "/api/candidatos": { candidatos: [], kpis: null, contas_parciais: false, dt_geracao: null } });
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.textContent).toMatch(/Nenhum candidato/); });
  });
  it("dispose cancela resposta tardia (não desenha em tela já trocada)", async () => {
    const dispose = await desenhar("visao-geral");
    dispose();
    await new Promise((r) => setTimeout(r, 10));
    expect(el.children).toHaveLength(0);
  });
});

describe("visão geral", () => {
  it("KPIs da spec, ranking e aviso de contas parciais", async () => {
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelectorAll(".kpi")).toHaveLength(7); });
    expect(el.querySelector("svg.grafico")).not.toBeNull();
    expect(el.textContent).toMatch(/parciais/);
    expect(chamou("grupo=missao_2026")).toBe(true);
  });
  it("'só indicados' reduz o ranking sem nova chamada à API", async () => {
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelectorAll("rect.marca")).toHaveLength(3); });
    const n = chamadas.length;
    const caixa = el.querySelector<HTMLInputElement>("input[type=checkbox]");
    caixa?.click();
    await vi.waitFor(() => { expect(el.querySelectorAll("rect.marca")).toHaveLength(2); });
    expect(chamadas.length).toBe(n);
  });
  it("seletor de comparação lista as comparações do contrato e refaz a busca com ela", async () => {
    await desenhar("visao-geral");
    const sel = await vi.waitFor(() => { const s = el.querySelector<HTMLSelectElement>("select[name=comparacao]"); expect(s).not.toBeNull(); return s as HTMLSelectElement; });
    expect([...sel.options].map((o) => o.text)).toEqual(["MBL 2022 → MBL 2026", "MBL 2022 → Missão 2026"]);
    sel.value = "mbl2022_missao2026";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(chamou("comparacao=mbl2022_missao2026")).toBe(true); });
  });
});

describe("mapa", () => {
  it("monta o mapa uma vez, colore com a escala da API e troca indicador sem remontar", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalledTimes(1); });
    const [, escala, meta] = mapaFalso.instancias[0]?.definirValores.mock.calls[0] as [unknown, { tipo: string }, { tipo: string }];
    expect(escala.tipo).toBe("quantil");
    expect(meta.tipo).toBe("taxa");
    const sel = el.querySelector<HTMLSelectElement>("select[name=indicador]") as HTMLSelectElement;
    sel.value = "swing";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalledTimes(2); });
    expect(mapaFalso.instancias).toHaveLength(1);
    expect(chamou("indicador=swing")).toBe(true);
  });
  it("níveis zona e H3 ficam desabilitados com explicação (sem PMTiles ainda)", async () => {
    await desenhar("mapa");
    const nivel = await vi.waitFor(() => { const s = el.querySelector<HTMLSelectElement>("select[name=nivel]"); expect(s).not.toBeNull(); return s as HTMLSelectElement; });
    const por = Object.fromEntries([...nivel.options].map((o) => [o.value, o.disabled]));
    expect(por).toEqual({ municipio: false, zona: true, h3: true });
  });
  it("painel lateral: escolher município busca /municipios/{ibge} e mostra os grupos", async () => {
    await desenhar("mapa");
    const sel = await vi.waitFor(() => { const s = el.querySelector<HTMLSelectElement>("select[name=municipio]"); expect(s?.options.length).toBeGreaterThan(1); return s as HTMLSelectElement; });
    sel.value = "2800308";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(el.querySelector(".painel-municipio")?.textContent).toContain("Aracaju"); });
    expect(el.querySelector(".painel-municipio")?.textContent).toContain("Missão 2026");
  });
  it("destruir libera o WebGL", async () => {
    const dispose = await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.instancias).toHaveLength(1); });
    dispose();
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.destruir).toHaveBeenCalled(); });
  });
});

describe("gastos", () => {
  it("KPIs, dispersão, empilhado e avisos de contas parciais e deflator", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelectorAll("svg.grafico")).toHaveLength(2); });
    expect(el.textContent).toMatch(/Contas de 2026 parciais/);
    expect(el.textContent).toMatch(/setembro de 2026/);
    expect(el.querySelector("dl.kpis")?.textContent).toMatch(/R\$/);
  });
  it("alternar contratado/pago redesenha a dispersão", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector("circle.marca")).not.toBeNull(); });
    const antes = el.querySelector("circle.marca")?.getAttribute("aria-label");
    const sel = el.querySelector<HTMLSelectElement>("select[name=base]") as HTMLSelectElement;
    sel.value = "pago";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(el.querySelector("circle.marca")?.getAttribute("aria-label")).not.toBe(antes); });
  });
});

describe("evolução 2022×2026", () => {
  it("três mapas (2022, 2026, diferença); 2022 e 2026 com as mesmas quebras", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(mapaFalso.instancias.filter((m) => m.definirValores.mock.calls.length > 0)).toHaveLength(3); });
    const escala = (i: number): { quebras: number[]; tipo: string } => (mapaFalso.instancias[i]?.definirValores.mock.calls[0] as unknown[])[1] as { quebras: number[]; tipo: string };
    expect(escala(0).quebras).toEqual(escala(1).quebras);
    expect(escala(2).tipo).toBe("divergente");
  });
  it("comparação por candidato e retenção", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.querySelector("svg.grafico")).not.toBeNull(); });
    expect(el.textContent).toMatch(/Retenção/);
    expect(el.textContent).toMatch(/mesmos candidatos/i);
  });
});

describe("candidato", () => {
  it("sem candidato escolhido, pede a escolha e lista os candidatos", async () => {
    await desenhar("candidato");
    const sel = await vi.waitFor(() => { const s = el.querySelector<HTMLSelectElement>("select[name=candidato]"); expect(s).not.toBeNull(); return s as HTMLSelectElement; });
    expect([...sel.options].map((o) => o.text)).toContain("Ana Souza");
    expect(el.textContent).toMatch(/Escolha um candidato/);
  });
  it("com deep-link mostra a ficha: votos por município, gastos e receitas", async () => {
    await desenhar("candidato", estado("candidato", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelector(".ficha")).not.toBeNull(); });
    expect(el.querySelector(".ficha")?.textContent).toContain("Ana Souza");
    expect(el.querySelectorAll("svg.grafico").length).toBeGreaterThanOrEqual(2);
    expect(chamou("sq_candidato=1")).toBe(true);
  });
});
