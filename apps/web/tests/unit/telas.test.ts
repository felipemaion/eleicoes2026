import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import grupos from "../fixtures/api/grupos.json";
import mapa from "../fixtures/api/mapa.json";
import pontos from "../fixtures/api/mapa-pontos.json";
import municipio from "../fixtures/api/municipio.json";
import { FILTROS_PADRAO, type Estado, type Tela as Chave } from "../../src/store";

type OpcoesFalsas = { aoSelecionar?: (id: string, nivel: string) => void; formatarTaxa?: (v: number) => string; ano?: number };
const mapaFalso = vi.hoisted(() => {
  const instancias: { definirValores: ReturnType<typeof vi.fn>; destruir: ReturnType<typeof vi.fn>; definirPontos: ReturnType<typeof vi.fn>; definirNivel: ReturnType<typeof vi.fn> }[] = [];
  const opcoes: OpcoesFalsas[] = [];
  return { instancias, opcoes, geometria: "pmtiles", niveis: ["municipio", "zona"] as string[] };
});
vi.mock("../../src/telas/mapa-embutido", () => ({
  UF_DA_DEMONSTRACAO: "SE",
  geometria: vi.fn(() => Promise.resolve(mapaFalso.geometria)),
  niveisDisponiveis: vi.fn(() => Promise.resolve(mapaFalso.niveis)),
  montarMapa: vi.fn((_area: unknown, _rotulo: string, opcoes: OpcoesFalsas = {}) => {
    const m = { definirValores: vi.fn(), definirPontos: vi.fn(), definirNivel: vi.fn(), destruir: vi.fn(), pronto: Promise.resolve(), estatisticas: () => ({ fontesCarregadas: 1, atualizacoesDeValores: 0 }) };
    mapaFalso.instancias.push(m);
    mapaFalso.opcoes.push(opcoes);
    return Promise.resolve(m);
  }),
}));

const ROTAS: Record<string, unknown> = {
  "/api/candidatos": candidatos, "/api/grupos": grupos, "/api/mapa": mapa, "/api/mapa/pontos": pontos,
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
  mapaFalso.opcoes.length = 0;
  mapaFalso.geometria = "pmtiles";
  mapaFalso.niveis = ["municipio", "zona"];
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
    simularApi({ "/api/candidatos": { total: 0, limite: 500, offset: 0, itens: [] } });
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
  it("KPIs derivados do contrato, ranking e aviso de contas parciais", async () => {
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelectorAll(".kpi")).toHaveLength(5); });
    expect(el.querySelector("svg.grafico")).not.toBeNull();
    expect(el.textContent).toMatch(/parciais/);
    expect(el.textContent).toMatch(/dt_geracao: 2026-10-07/);
    expect(chamou("grupo=missao_2026")).toBe(true);
  });
  it("pede o teto de 500 candidaturas para a soma dos KPIs ser completa", async () => {
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(chamou("/api/candidatos?")).toBe(true); });
    expect(chamadas.find((c) => c.startsWith("/api/candidatos?"))).toContain("limite=500");
  });
  it("traduz o cargo do filtro para o enum da API", async () => {
    await desenhar("visao-geral", estado("visao-geral", { cargo: "deputado_federal", uf: "SE" }));
    await vi.waitFor(() => { expect(chamou("cargo=DEPUTADO+FEDERAL")).toBe(true); });
  });
});

describe("mapa", () => {
  const SE = { uf: "SE" } as const;
  it("monta o mapa uma vez, colore com as quebras da API e troca indicador sem remontar", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalledTimes(1); });
    const [, escala, meta] = mapaFalso.instancias[0]?.definirValores.mock.calls[0] as [unknown, { tipo: string }, { tipo: string; unidade: string }];
    expect(escala.tipo).toBe("limiar");
    expect(meta).toMatchObject({ tipo: "taxa", unidade: "‰" });
    const sel = el.querySelector<HTMLSelectElement>("select[name=indicador]") as HTMLSelectElement;
    sel.value = "pct_validos";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalledTimes(2); });
    expect(mapaFalso.instancias).toHaveLength(1);
    expect(chamou("indicador=pct_validos")).toBe(true);
  });
  it("mapa e comparativo mandam cargo obrigatório; 'todos' vira deputado federal, com aviso", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(chamou("/api/mapa?")).toBe(true); });
    expect(chamadas.find((c) => c.startsWith("/api/mapa?"))).toContain("cargo=DEPUTADO+FEDERAL");
    expect(el.textContent).toMatch(/exige um cargo/);
  });
  it("formata a taxa pela unidade da API (‰), não como fração", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalled(); });
    expect(mapaFalso.opcoes[0]?.formatarTaxa?.(12.5)).toBe("12,5 ‰");
  });
  it("zona só habilita com PMTiles do ano e UF escolhida; H3 segue desabilitado", async () => {
    await desenhar("mapa", estado("mapa", SE));
    const nivel = await vi.waitFor(() => { const s = el.querySelector<HTMLSelectElement>("select[name=nivel]"); expect(s).not.toBeNull(); return s as HTMLSelectElement; });
    await vi.waitFor(() => { expect([...nivel.options].find((o) => o.value === "zona")?.disabled).toBe(false); });
    expect([...nivel.options].find((o) => o.value === "h3")?.disabled).toBe(true);
    nivel.value = "zona";
    nivel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirNivel).toHaveBeenCalledWith("zona"); });
    await vi.waitFor(() => { expect(chamadas.filter((c) => c.startsWith("/api/mapa?") && c.includes("nivel=zona"))).toHaveLength(1); });
  });
  it("sem UF ou sem tiles do ano, zona fica desabilitada", async () => {
    mapaFalso.niveis = ["municipio"];
    await desenhar("mapa", estado("mapa", SE));
    await vi.waitFor(() => { expect(mapaFalso.instancias).toHaveLength(1); });
    await new Promise((r) => setTimeout(r, 10));
    expect(el.querySelector<HTMLOptionElement>("select[name=nivel] option[value=zona]")?.disabled).toBe(true);
  });
  it("sem PMTiles (demonstração) e UF ≠ SE, avisa que só Sergipe é desenhado", async () => {
    mapaFalso.geometria = "demonstracao";
    await desenhar("mapa", estado("mapa", { uf: "BA" }));
    await vi.waitFor(() => { expect(el.textContent).toMatch(/Geometria de demonstração/); });
  });
  it("clicar num município (evento do mapa) abre o painel com o resumo por grupo e cargo e leva o foco", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.opcoes).toHaveLength(1); });
    mapaFalso.opcoes[0]?.aoSelecionar?.("2800308", "municipio");
    await vi.waitFor(() => { expect(el.querySelector(".painel-municipio")?.textContent).toContain("Aracaju"); });
    const painel = el.querySelector(".painel-municipio") as HTMLElement;
    expect(painel.textContent).toContain("Missão 2026");
    expect(painel.textContent).toContain("14,88 ‰");
    expect(painel.textContent).toContain("sem dado"); // deputado estadual sem aptos suficientes
    expect(document.activeElement).toBe(painel.querySelector("h2"));
    expect(chamou("/api/municipios/2800308")).toBe(true);
  });
  it("chave de zona (IBGE-zona) abre o painel do município dela", async () => {
    await desenhar("mapa", estado("mapa", SE));
    await vi.waitFor(() => { expect(mapaFalso.opcoes).toHaveLength(1); });
    mapaFalso.opcoes[0]?.aoSelecionar?.("2800308-12", "zona");
    await vi.waitFor(() => { expect(chamou("/api/municipios/2800308")).toBe(true); });
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
  it("KPIs em ‰ com Δ e retenção; sem gráfico por candidato (o contrato não o traz)", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.querySelector("dl.kpis")).not.toBeNull(); });
    expect(el.querySelector("dl.kpis")?.textContent).toMatch(/Retenção/);
    expect(el.querySelector("dl.kpis")?.textContent).toMatch(/6,1 ‰/);
    expect(el.querySelector("svg.grafico")).toBeNull();
  });
  it("cargo 'todos' vai como DEPUTADO FEDERAL (o endpoint exige cargo)", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(chamou("/api/comparativo?")).toBe(true); });
    expect(chamadas.find((c) => c.startsWith("/api/comparativo?"))).toContain("cargo=DEPUTADO+FEDERAL");
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

describe("mapa — corridas de requisição", () => {
  type Resp = { ok: boolean; status: number; json: () => Promise<unknown> };
  /** fetch controlável: cada chamada a `caminho` fica pendente até `resolver`/`falhar`. */
  function controlar(caminho: string): { resolver(i: number, corpo: unknown): void; falhar(i: number): void; n(): number } {
    const pend: ((r: Resp) => void)[] = [];
    const base = (globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<Resp>);
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if ((url.split("?")[0] ?? url) !== caminho) return base(url, init);
      return new Promise<Resp>((res) => { pend.push(res); });
    }));
    return {
      resolver: (i, corpo) => { pend[i]?.({ ok: true, status: 200, json: () => Promise.resolve(corpo) }); },
      falhar: (i) => { pend[i]?.({ ok: false, status: 500, json: () => Promise.resolve({}) }); },
      n: () => pend.length,
    };
  }
  const trocar = (nome: string, valor: string): void => {
    const s = el.querySelector<HTMLSelectElement>(`select[name=${nome}]`) as HTMLSelectElement;
    s.value = valor;
    s.dispatchEvent(new Event("change"));
  };

  it("erro de requisição de /mapa obsoleta não sobrescreve o mapa válido", async () => {
    const c = controlar("/api/mapa");
    await desenhar("mapa");
    await vi.waitFor(() => { expect(c.n()).toBe(1); });
    trocar("indicador", "pct_validos");
    await vi.waitFor(() => { expect(c.n()).toBe(2); });
    c.resolver(1, mapa);
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirValores).toHaveBeenCalledTimes(1); });
    c.falhar(0);
    await new Promise((r) => setTimeout(r, 20));
    expect(el.querySelector(".estado [role=alert]")).toBeNull();
    expect(el.textContent).not.toMatch(/falhou/);
  });

  it("pontos antigos não substituem os novos (nem o ramo de densidade desligada)", async () => {
    const c = controlar("/api/mapa/pontos");
    await desenhar("mapa", estado("mapa", { uf: "SE" }));
    await vi.waitFor(() => { expect(c.n()).toBe(1); });
    trocar("indicador", "pct_validos");
    await vi.waitFor(() => { expect(c.n()).toBe(2); });
    const m = mapaFalso.instancias[0];
    c.resolver(1, { pontos: [{ lat: 1, lon: 1, votos: 7 }], truncado: false });
    await vi.waitFor(() => { expect(m?.definirPontos).toHaveBeenCalledTimes(1); });
    c.resolver(0, { pontos: [{ lat: 2, lon: 2, votos: 9 }], truncado: false });
    await new Promise((r) => setTimeout(r, 20));
    expect(m?.definirPontos).toHaveBeenCalledTimes(1);
    // desligar a densidade com um pedido ainda pendente: o pedido velho não pode religar os pontos
    trocar("indicador", "penetracao");
    await vi.waitFor(() => { expect(c.n()).toBe(3); });
    const dens = el.querySelector<HTMLInputElement>("input[name=densidade]") as HTMLInputElement;
    dens.checked = false;
    dens.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(m?.definirPontos).toHaveBeenCalledTimes(2); });
    c.resolver(2, { pontos: [{ lat: 3, lon: 3, votos: 1 }], truncado: false });
    await new Promise((r) => setTimeout(r, 20));
    expect(m?.definirPontos).toHaveBeenCalledTimes(2);
    expect((m?.definirPontos.mock.calls[1]?.[0] as { features: unknown[] }).features).toHaveLength(0);
  });

  it("resumo de município antigo não sobrescreve o mais novo", async () => {
    const c = controlar("/api/municipios/2800308");
    await desenhar("mapa");
    await vi.waitFor(() => { expect(mapaFalso.opcoes).toHaveLength(1); });
    const escolher = mapaFalso.opcoes[0]?.aoSelecionar as (id: string, n: string) => void;
    escolher("2800308", "municipio");
    await vi.waitFor(() => { expect(c.n()).toBe(1); });
    escolher("2800100", "municipio"); // não existe nas rotas: 500 imediato
    await vi.waitFor(() => { expect(el.querySelector(".painel-municipio [role=alert]")).not.toBeNull(); });
    c.resolver(0, municipio);
    await new Promise((r) => setTimeout(r, 20));
    expect(el.querySelector(".painel-municipio")?.textContent).not.toContain("Aracaju");
  });
});
