import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import grupos from "../fixtures/api/grupos.json";
import mapa from "../fixtures/api/mapa.json";
import pontos from "../fixtures/api/mapa-pontos.json";
import pessoas from "../fixtures/api/pessoas.json";
import municipio from "../fixtures/api/municipio.json";
import { FILTROS_PADRAO, type Estado, type Tela as Chave } from "../../src/store";

type OpcoesFalsas = { aoSelecionar?: (id: string, nivel: string) => void; formatarTaxa?: (v: number) => string; ano?: number };
const mapaFalso = vi.hoisted(() => {
  const instancias: { definirValores: ReturnType<typeof vi.fn>; destruir: ReturnType<typeof vi.fn>; definirPontos: ReturnType<typeof vi.fn>; definirNivel: ReturnType<typeof vi.fn>; definirAbrangencia: ReturnType<typeof vi.fn> }[] = [];
  const opcoes: OpcoesFalsas[] = [];
  return { instancias, opcoes, geometria: "pmtiles", niveis: ["municipio", "zona"] as string[] };
});
vi.mock("../../src/telas/mapa-embutido", () => ({
  UF_DA_DEMONSTRACAO: "SE",
  geometria: vi.fn(() => Promise.resolve(mapaFalso.geometria)),
  niveisDisponiveis: vi.fn(() => Promise.resolve(mapaFalso.niveis)),
  montarMapa: vi.fn((_area: unknown, _rotulo: string, opcoes: OpcoesFalsas = {}) => {
    const m = { definirValores: vi.fn(), definirPontos: vi.fn(), definirNivel: vi.fn(), definirAbrangencia: vi.fn(), destruir: vi.fn(), pronto: Promise.resolve(), estatisticas: () => ({ fontesCarregadas: 1, atualizacoesDeValores: 0 }) };
    mapaFalso.instancias.push(m);
    mapaFalso.opcoes.push(opcoes);
    return Promise.resolve(m);
  }),
}));

const ROTAS: Record<string, unknown> = {
  "/api/candidatos": candidatos, "/api/grupos": grupos, "/api/mapa": mapa, "/api/mapa/pontos": pontos,
  "/api/gastos": gastos, "/api/comparativo": comparativo, "/api/candidatos/2026/1": ficha, "/api/municipios/2800308": municipio,
  "/api/evolucao/pessoas": pessoas,
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
  it("reserva o espaço (aria-busy) enquanto carrega, avisa a sobreposição e depois mostra o conteúdo; h1 sempre presente", async () => {
    const { criarSobreposicao, definirSobreposicaoGlobal } = await import("../../src/componentes/ui/sobreposicao");
    const so = criarSobreposicao(document.body);
    definirSobreposicaoGlobal(so);
    await desenhar("visao-geral");
    expect(el.querySelector("h1")?.textContent).toBe("Visão geral");
    expect(el.querySelector("[aria-busy=true]")).not.toBeNull();
    await vi.waitFor(() => { expect(el.querySelector("[aria-busy=true]")).toBeNull(); });
    definirSobreposicaoGlobal(null);
  });
  it("erro da API vira alerta com 'Tentar novamente' que refaz a busca", async () => {
    simularApi({ "/api/candidatos": new Error("x") });
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelector("[role=alert]")).not.toBeNull(); });
    expect(el.querySelector("[role=alert]")?.textContent).toMatch(/Não foi possível/);
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
    expect(el.textContent).toMatch(/07\/10\/2026/);
    expect(chamou("grupo=missao_2026")).toBe(true);
  });
  it("cada KPI com texto público ganha um '?' acessível; subtítulo público no topo", async () => {
    await desenhar("visao-geral");
    await vi.waitFor(() => { expect(el.querySelectorAll(".kpi button.ajuda-botao").length).toBeGreaterThanOrEqual(3); });
    expect(el.querySelector(".subtitulo")?.textContent).toMatch(/Missão/);
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
  it("mapa manda o cargo do filtro (padrão: deputado federal), sem aviso de cargo faltando", async () => {
    await desenhar("mapa");
    await vi.waitFor(() => { expect(chamou("/api/mapa?")).toBe(true); });
    expect(chamadas.find((c) => c.startsWith("/api/mapa?"))).toContain("cargo=DEPUTADO+FEDERAL");
    expect(el.textContent).not.toMatch(/exige um cargo/);
  });
  it("candidato fixado: ano, cargo e UF vêm da ficha (não dos filtros), sem grupo, e o mapa enquadra a UF", async () => {
    await desenhar("mapa", estado("mapa", { uf: "SP", cargo: "presidente", candidato: "2026:1" }));
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirAbrangencia).toHaveBeenCalled(); });
    const url = chamadas.find((c) => c.startsWith("/api/mapa?")) ?? "";
    expect(url).toContain("sq_candidato=1");
    expect(url).toContain("cargo=DEPUTADO+FEDERAL");
    expect(url).toContain("uf=SE");
    expect(url).not.toContain("grupo=");
    expect(mapaFalso.instancias[0]?.definirAbrangencia).toHaveBeenCalledWith("28", expect.any(Array));
    expect(el.querySelector(".mapa-foco")?.textContent).toMatch(/Mostrando só onde disputou: Sergipe/);
  });
  it("presidente: mapa nacional sem UF, sem esmaecer, com os votos do exterior à parte", async () => {
    const pres = { ...ficha, candidato: { ...ficha.candidato, cargo: "PRESIDENTE", sg_uf: "BR", abrangencia: { tipo: "pais", uf: null } } };
    simularApi({ "/api/candidatos/2026/1": pres, "/api/mapa": { ...mapa, votos_fora_do_mapa: 8580 } });
    await desenhar("mapa", estado("mapa", { cargo: "presidente", candidato: "2026:1" }));
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirAbrangencia).toHaveBeenCalledWith(null, null); });
    const url = chamadas.find((c) => c.startsWith("/api/mapa?")) ?? "";
    expect(url).toContain("cargo=PRESIDENTE");
    expect(url).not.toContain("uf=");
    await vi.waitFor(() => { expect(el.textContent).toContain("Votos no exterior: 8.580 (fora do mapa)."); });
    expect(el.querySelector(".mapa-foco")?.textContent).toMatch(/Brasil inteiro/);
    expect(el.querySelector('[role="alert"]')).toBeNull();
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
    expect(painel.textContent).toContain("14,88");
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
    await vi.waitFor(() => { expect(el.querySelectorAll("svg.grafico")).toHaveLength(3); });
    expect(el.textContent).toMatch(/Contas de 2026 parciais/);
    expect(el.textContent).toMatch(/set\/2026/);
    expect(el.querySelector("dl.kpis")?.textContent).toMatch(/R\$/);
  });
  it("alternar contratado/pago redesenha a dispersão", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa circle.marca")).not.toBeNull(); });
    const antes = el.querySelector(".grafico-despesa circle.marca")?.getAttribute("aria-label");
    const sel = el.querySelector<HTMLSelectElement>("select[name=base]") as HTMLSelectElement;
    sel.value = "pago";
    sel.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa circle.marca")?.getAttribute("aria-label")).not.toBe(antes); });
  });
});

describe("gastos — hover, busca e referência", () => {
  const balao = (): string => document.querySelector(".tooltip-flutuante:not([hidden])")?.textContent ?? "";
  it("cada ponto abre tooltip com partido, UF, cargo, votos, despesas, custo por voto e resultado", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa circle.marca")).not.toBeNull(); });
    el.querySelector('.grafico-despesa circle[data-id="1"]')?.dispatchEvent(new MouseEvent("mouseenter", { clientX: 10, clientY: 10 }));
    for (const t of ["Ana Souza", "MISSÃO (14)", "SE", "deputado federal", "18.049", "Despesa contratada", "Despesa paga", "Custo por voto", "eleito", "62,5%"]) expect(balao()).toContain(t);
    expect(chamou("/api/candidatos?")).toBe(false);
  });
  it("mostra a mediana de custo por voto como linha de referência", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa line.referencia")).not.toBeNull(); });
    expect(el.querySelector(".grafico-despesa .referencia-rotulo")?.textContent).toMatch(/mediana/i);
  });
  it("a busca realça o candidato no gráfico (sem acento) e avisa quando não acha", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa circle.marca")).not.toBeNull(); });
    const q = el.querySelector<HTMLInputElement>("input[name=busca-gastos]") as HTMLInputElement;
    q.value = "bruno";
    q.dispatchEvent(new Event("input"));
    expect(el.querySelector('.grafico-despesa circle[data-id="2"]')?.classList.contains("destaque")).toBe(true);
    expect(el.querySelector('.grafico-despesa circle[data-id="1"]')?.classList.contains("atenuado")).toBe(true);
    expect(el.querySelector(".busca-gastos-estado")?.textContent).toContain("1 candidato");
    q.value = "zzzz";
    q.dispatchEvent(new Event("input"));
    expect(el.querySelector(".busca-gastos-estado")?.textContent).toMatch(/Nenhum candidato/);
    expect(el.querySelectorAll("circle.destaque")).toHaveLength(0);
  });
  it("a mudança de base mantém o destaque da busca", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-despesa circle.marca")).not.toBeNull(); });
    const q = el.querySelector<HTMLInputElement>("input[name=busca-gastos]") as HTMLInputElement;
    q.value = "ana";
    q.dispatchEvent(new Event("input"));
    const sel = el.querySelector<HTMLSelectElement>("select[name=base]") as HTMLSelectElement;
    sel.value = "pago";
    sel.dispatchEvent(new Event("change"));
    expect(el.querySelector('.grafico-despesa circle[data-id="1"]')?.classList.contains("destaque")).toBe(true);
  });
  it("barras de receita têm hover com fonte e valor", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector("rect.marca")).not.toBeNull(); });
    el.querySelector("rect.marca")?.dispatchEvent(new MouseEvent("mouseenter", { clientX: 5, clientY: 5 }));
    expect(balao()).toMatch(/R\$/);
  });
});

describe("financiamento — receitas", () => {
  const balao = (): string => document.querySelector(".tooltip-flutuante:not([hidden])")?.textContent ?? "";
  it("tela chama-se Financiamento e mostra KPIs de receita com fonte e ajuda", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-receita circle.marca")).not.toBeNull(); });
    expect(el.querySelector("h1")?.textContent).toBe("Financiamento");
    const kpis = el.querySelector("dl.kpis")?.textContent ?? "";
    for (const t of ["Receita total do grupo", "Receita por voto", "% pessoas físicas", "Saldo da campanha"]) expect(kpis).toContain(t);
    expect(el.querySelectorAll("dl.kpis .fonte-linha").length).toBeGreaterThan(5);
  });
  it("faixa honesta de receita quando há repasse de doador desconhecido", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.textContent).toMatch(/entre R\$\s280\.000,00 e R\$\s290\.000,00/); });
  });
  it("dispersão de receita: hover com receita, saldo e foto; mediana de receita por voto como referência", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-receita circle.marca")).not.toBeNull(); });
    el.querySelector('.grafico-receita circle[data-id="1"]')?.dispatchEvent(new MouseEvent("mouseenter", { clientX: 10, clientY: 10 }));
    for (const t of ["Ana Souza", "Receita total", "Receita por voto", "Saldo (receita − despesa contratada)", "% pessoas físicas"]) expect(balao()).toContain(t);
    expect(document.querySelector(".tooltip-flutuante:not([hidden]) img")).not.toBeNull();
    expect(el.querySelector(".grafico-receita .referencia-rotulo")?.textContent).toMatch(/mediana.*receita por voto/i);
  });
  it("a busca realça o candidato nas duas dispersões", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector(".grafico-receita circle.marca")).not.toBeNull(); });
    const q = el.querySelector<HTMLInputElement>("input[name=busca-gastos]") as HTMLInputElement;
    q.value = "bruno";
    q.dispatchEvent(new Event("input"));
    expect(el.querySelector('.grafico-receita circle[data-id="2"]')?.classList.contains("destaque")).toBe(true);
    expect(el.querySelector('.grafico-despesa circle[data-id="2"]')?.classList.contains("destaque")).toBe(true);
  });
  it("comparação 2022×2026: tabela com 2022 corrigido, mês-base e variação", async () => {
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.querySelector("table.tabela-comparativo-receitas")).not.toBeNull(); });
    const t = el.querySelector("table.tabela-comparativo-receitas")?.textContent ?? "";
    expect(t).toContain("set/2026");
    expect(t).toMatch(/Receita total.*260\.000,00.*200\.000,00.*290\.000,00.*\+11,5%/);
    expect(t).toMatch(/\+46,2 p\.p\./);
    expect(el.textContent).toMatch(/contas de 2026 ainda são parciais/);
  });
  it("sem receita declarada: avisa em vez de desenhar zeros", async () => {
    simularApi({ "/api/gastos": { ...gastos, receitas: null, por_candidato: gastos.por_candidato.map((c) => ({ ...c, receita_total: null })) } });
    await desenhar("gastos");
    await vi.waitFor(() => { expect(el.textContent).toMatch(/Nenhum candidato do recorte tem receita declarada/); });
    expect(el.querySelector(".grafico-receita")).toBeNull();
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
  it("o comparativo manda sempre o cargo (padrão: DEPUTADO FEDERAL)", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(chamou("/api/comparativo?")).toBe(true); });
    expect(chamadas.find((c) => c.startsWith("/api/comparativo?"))).toContain("cargo=DEPUTADO+FEDERAL");
  });
});

describe("evolução — comparador de lados (T-W20)", () => {
  const urlComparativo = (): string => chamadas.filter((c) => c.startsWith("/api/comparativo?")).at(-1) ?? "";
  it("frase-resumo no topo, dois cartões 2022 → 2026 e nenhuma lista longa de candidatos", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.querySelector(".frase-resumo")).not.toBeNull(); });
    expect(el.querySelector(".frase-resumo")?.textContent).toMatch(/Comparando MBL 2022 \(2022\) com Partido Missão 2026 \(2026\) · Deputado federal · Brasil/);
    expect([...el.querySelectorAll(".cartao-lado h2")].map((x) => x.textContent)).toEqual(["2022", "2026"]);
    expect(el.querySelector(".lista-pessoas, .pessoa-item")).toBeNull();
    expect(chamadas.some((c) => c.startsWith("/api/evolucao/pessoas"))).toBe(false);
    expect(urlComparativo()).toContain("comparacao=");
  });
  it("com a contagem da API na frase e KPIs rotulados 2022 e 2026", async () => {
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.querySelector("dl.kpis")).not.toBeNull(); });
    expect(el.querySelector(".frase-contagem")?.textContent).toContain("3 candidaturas → 3 candidaturas");
    const kpis = el.querySelector("dl.kpis")?.textContent ?? "";
    expect(kpis).toContain("Penetração em 2022");
    expect(kpis).toContain("Penetração em 2026");
    expect(el.querySelector("details.notas-dados summary")?.textContent).toBe("Notas sobre os dados");
  });
  it("Aplicar grava o lado na URL (nomes curtos) e 'Limpar' volta ao padrão", async () => {
    window.location.hash = "";
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.querySelectorAll(".cartao-lado")).toHaveLength(2); });
    (el.querySelectorAll("button[data-acao=alterar]")[1] as HTMLButtonElement).click();
    const sel = el.querySelectorAll<HTMLSelectElement>("select[name=grupo]")[1] as HTMLSelectElement;
    sel.value = "mbl_2026";
    sel.dispatchEvent(new Event("change"));
    (el.querySelectorAll("button[data-acao=aplicar]")[1] as HTMLButtonElement).click();
    expect(decodeURIComponent(window.location.hash)).toContain("para=g:mbl_2026");
  });
  it("lado de candidatos com o outro em grupo (misto) vai por lado ao /comparativo; nomes vêm da ficha", async () => {
    await desenhar("evolucao", estado("evolucao", { de: "c:1", para: "g:missao_2026" }));
    await vi.waitFor(() => { expect(el.querySelector("dl.kpis")).not.toBeNull(); });
    expect(urlComparativo()).toContain("sq_2022=1");
    expect(urlComparativo()).toContain("grupo_2026=missao_2026");
    expect(urlComparativo()).not.toContain("comparacao=");
    expect(chamadas).toContain("/api/candidatos/2022/1");
  });
  it("422 do /comparativo vira mensagem curta, sem quebrar a tela; os cartões continuam", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      chamadas.push(url);
      const caminho = url.split("?")[0] ?? url;
      if (caminho === "/api/comparativo") return Promise.resolve({ ok: false, status: 422, json: () => Promise.resolve({}) });
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(ROTAS[caminho]) });
    }));
    await desenhar("evolucao");
    await vi.waitFor(() => { expect(el.textContent).toContain("Não há o que comparar com esta escolha"); });
    expect(el.querySelectorAll(".cartao-lado")).toHaveLength(2);
    expect(el.querySelector("[role=alert]")).toBeNull();
  });
});

describe("recorte segue o candidato", () => {
  it("ficha aberta ajusta cargo/UF/ano dos filtros ao candidato (deep-link só com cand=)", async () => {
    const { definirAjustadorDeRecorte } = await import("../../src/telas/recorte");
    const ajustar = vi.fn();
    definirAjustadorDeRecorte(ajustar);
    await desenhar("candidato", estado("candidato", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelector(".ficha")).not.toBeNull(); });
    expect(ajustar).toHaveBeenCalledWith(expect.objectContaining({ cargo: "deputado_federal", uf: "SE", ano: 2026 }));
    // a lista do seletor vem do recorte do próprio candidato, não do filtro padrão
    expect(chamou("uf=SE")).toBe(true);
    definirAjustadorDeRecorte(null);
  });
  it("mapa com candidato também ajusta", async () => {
    const { definirAjustadorDeRecorte } = await import("../../src/telas/recorte");
    const ajustar = vi.fn();
    definirAjustadorDeRecorte(ajustar);
    await desenhar("mapa", estado("mapa", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(ajustar).toHaveBeenCalled(); });
    definirAjustadorDeRecorte(null);
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
  it("ficha rastreável: gastos completos, custo com e sem repasses explicado, receita por fonte", async () => {
    await desenhar("candidato", estado("candidato", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelector(".ficha-gastos")).not.toBeNull(); });
    const t = el.querySelector(".ficha-gastos")?.textContent ?? "";
    for (const x of ["Contratado", "Pago", "Dívida", "223.000", "180.000", "43.000", "Repasses", "sem repasses", "com repasses", "14,02", "Repasses são dinheiro transferido"]) expect(t).toContain(x);
  });
  it("ficha: botões para as páginas oficiais do TSE abrem em nova aba, com aviso quando não verificados", async () => {
    await desenhar("candidato", estado("candidato", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelector(".ficha-links")).not.toBeNull(); });
    const links = [...el.querySelectorAll<HTMLAnchorElement>(".ficha-links a")];
    expect(links.map((a) => a.textContent)).toEqual(expect.arrayContaining([expect.stringContaining("resultados.tse.jus.br"), expect.stringContaining("DivulgaCandContas")]));
    for (const a of links) { expect(a.target).toBe("_blank"); expect(a.rel).toContain("noopener"); expect(a.href).toMatch(/^https:\/\//); }
    expect(el.querySelector(".ficha-links")?.textContent).toContain("Confira o número do candidato");
  });
  it("cada bloco de números tem 'fonte': dataset, data de geração, regra e link da metodologia", async () => {
    await desenhar("candidato", estado("candidato", { candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelectorAll(".fonte-botao").length).toBeGreaterThanOrEqual(2); });
    const botoes = [...el.querySelectorAll<HTMLButtonElement>(".fonte-botao")];
    const gastos = botoes.find((b) => b.closest(".ficha-gastos")) as HTMLButtonElement;
    gastos.focus();
    gastos.dispatchEvent(new FocusEvent("focus"));
    const painel = gastos.parentElement?.querySelector<HTMLElement>(".fonte-painel") as HTMLElement;
    expect(painel.hidden).toBe(false);
    for (const x of ["prestacao_contas", "07/10/2026", "VR_DESPESA_CONTRATADA", "Metodologia"]) expect(painel.textContent).toContain(x);
    expect(painel.querySelector<HTMLAnchorElement>("a[href*='indicadores.md']")).not.toBeNull();
  });
  it("presidente (Renan Santos): ficha e mapa nacional carregam mesmo com filtros de outra UF e fora da lista do recorte", async () => {
    const pres = { ...ficha, candidato: { ...ficha.candidato, nm_urna: "RENAN SANTOS", cargo: "PRESIDENTE", sg_uf: "BR", abrangencia: { tipo: "pais", uf: null } } };
    simularApi({ "/api/candidatos/2026/1": pres, "/api/candidatos": { ...candidatos, total: 0, itens: [] }, "/api/mapa": { ...mapa, votos_fora_do_mapa: 8580 } });
    await desenhar("candidato", estado("candidato", { uf: "SP", candidato: "2026:1" }));
    await vi.waitFor(() => { expect(el.querySelector(".ficha")).not.toBeNull(); });
    expect(el.querySelector('[role="alert"]')).toBeNull();
    expect([...el.querySelectorAll<HTMLOptionElement>("select[name=candidato] option")].map((o) => o.text)).toContain("RENAN SANTOS");
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirAbrangencia).toHaveBeenCalledWith(null, null); });
    const url = chamadas.find((c) => c.startsWith("/api/mapa?")) ?? "";
    expect(url).toContain("cargo=PRESIDENTE");
    expect(url).not.toContain("uf=");
    await vi.waitFor(() => { expect(el.textContent).toContain("Votos no exterior: 8.580"); });
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
    // A densidade nasce desligada; o usuário liga.
    const dens = el.querySelector<HTMLInputElement>("input[name=densidade]") as HTMLInputElement;
    expect(dens.checked).toBe(false);
    await vi.waitFor(() => { expect(mapaFalso.instancias[0]?.definirPontos).toHaveBeenCalledTimes(1); });
    dens.checked = true;
    dens.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(c.n()).toBe(1); });
    trocar("indicador", "pct_validos");
    await vi.waitFor(() => { expect(c.n()).toBe(2); });
    const m = mapaFalso.instancias[0];
    c.resolver(1, { pontos: [{ lat: 1, lon: 1, votos: 7 }], truncado: false });
    await vi.waitFor(() => { expect(m?.definirPontos).toHaveBeenCalledTimes(2); });
    c.resolver(0, { pontos: [{ lat: 2, lon: 2, votos: 9 }], truncado: false });
    await new Promise((r) => setTimeout(r, 20));
    expect(m?.definirPontos).toHaveBeenCalledTimes(2);
    // desligar a densidade com um pedido ainda pendente: o pedido velho não pode religar os pontos
    trocar("indicador", "penetracao");
    await vi.waitFor(() => { expect(c.n()).toBe(3); });
    dens.checked = false;
    dens.dispatchEvent(new Event("change"));
    await vi.waitFor(() => { expect(m?.definirPontos).toHaveBeenCalledTimes(3); });
    c.resolver(2, { pontos: [{ lat: 3, lon: 3, votos: 1 }], truncado: false });
    await new Promise((r) => setTimeout(r, 20));
    expect(m?.definirPontos).toHaveBeenCalledTimes(3);
    expect((m?.definirPontos.mock.calls[2]?.[0] as { features: unknown[] }).features).toHaveLength(0);
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

describe("como ler este painel", () => {
  it("renderiza o README público copiado no build", async () => {
    await desenhar("como-ler");
    await vi.waitFor(() => { expect(el.querySelector("article.como-ler h2")?.textContent).toBe("Como ler este painel"); });
    expect(el.querySelector("h1")?.textContent).toBe("Como ler este painel");
    expect(el.querySelectorAll("article table").length).toBeGreaterThan(0);
  });
});
