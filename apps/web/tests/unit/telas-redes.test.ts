import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import grupos from "../fixtures/api/grupos.json";
import correlacoes from "../fixtures/api/redes-correlacoes.json";
import redes from "../fixtures/api/redes.json";
import serie1 from "../fixtures/api/redes-serie.json";
import serie2 from "../fixtures/api/redes-serie-2pontos.json";
import { FILTROS_PADRAO, type Estado } from "../../src/store";

type Resp = { status: number; corpo: unknown };
const ok = (corpo: unknown): Resp => ({ status: 200, corpo });
let el: HTMLElement;
let chamadas: string[];

function simular(rotas: Record<string, Resp>): void {
  chamadas = [];
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    chamadas.push(url);
    const r = rotas[url.split("?")[0] ?? url] ?? { status: 404, corpo: {} };
    return Promise.resolve({ ok: r.status < 400, status: r.status, json: () => Promise.resolve(r.corpo) });
  }));
}
const padrao = (serie: unknown = serie1): Record<string, Resp> => ({
  "/api/redes": ok(redes), "/api/redes/correlacoes": ok(correlacoes), "/api/redes/serie": ok(serie), "/api/grupos": ok(grupos),
});
const estado: Estado = { tela: "redes", filtros: { ...FILTROS_PADRAO, uf: "SE" } };

beforeEach(() => { document.body.innerHTML = '<main id="m"></main>'; el = document.getElementById("m") as HTMLElement; });
afterEach(() => { vi.unstubAllGlobals(); });

async function desenhar(): Promise<() => void> {
  const { TELAS_POR_CHAVE } = await import("../../src/telas");
  return TELAS_POR_CHAVE.redes.render(el, estado);
}

describe("tela Redes sociais", () => {
  it("diz o que compara, mostra KPIs com fonte, dispersão clicável e rankings compactos", async () => {
    simular(padrao());
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector(".resumo-redes")).not.toBeNull(); });
    expect(el.querySelector(".resumo-redes")?.textContent).toMatch(/^Instagram de 14 candidaturas do .* · Dep\. federal · SE — 10 com perfil público, 4 indisponíveis\.$/);
    expect(chamadas.find((c) => c.startsWith("/api/redes?"))).toMatch(/grupo=missao_2026.*cargo=DEPUTADO\+FEDERAL.*uf=SE|uf=SE.*cargo/);
    expect(chamadas.some((c) => c.includes("ano="))).toBe(false);
    expect(el.querySelector("dl.kpis")?.querySelectorAll(".kpi")).toHaveLength(6);
    expect(el.querySelectorAll(".grafico-redes-dispersao circle.marca")).toHaveLength(10);
    expect(el.querySelector(".grafico-redes-dispersao polyline.reta-ajuste")).not.toBeNull();
    expect(el.querySelector('.grafico-redes-dispersao circle.marca.com-link[role="button"]')).not.toBeNull();
    for (const t of ["Relação moderada", "não prova causa", "Fora dos números"]) expect(el.textContent).toContain(t);
    expect(el.querySelectorAll(".rankings-redes svg.grafico")).toHaveLength(3);
    expect(el.querySelectorAll(".ranking-Seguidores rect.marca")).toHaveLength(10);
    expect(el.textContent).toMatch(/coletado em 08\/10\/2026/);
  });

  it("série com 1 ponto mostra o número e a nota; com 2 pontos desenha a linha e o resumo", async () => {
    simular(padrao(serie1));
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector(".serie-numero")).not.toBeNull(); });
    expect(el.querySelector(".serie-numero")?.textContent).toMatch(/52\.000 seguidores em @anasouza_14/);
    expect(el.querySelector(".serie-seguidores")?.textContent).toContain("A série cresce a cada dia.");
    expect(el.querySelector(".serie-seguidores svg")).toBeNull();
    document.body.innerHTML = '<main id="m"></main>';
    el = document.getElementById("m") as HTMLElement;
    simular(padrao(serie2));
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector(".grafico-redes-serie path.linha-serie")).not.toBeNull(); });
    expect(el.querySelector(".serie-resumo")?.textContent).toContain("+340 seguidores (+0,65 %) em 1 dia");
    expect(el.querySelectorAll(".grafico-redes-serie circle.marca")).toHaveLength(2);
  });

  it("buscar um perfil indisponível mostra 'Perfil indisponível' com link do TSE, nunca zero, e não pede série", async () => {
    simular(padrao());
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector("input[name=busca-redes]")).not.toBeNull(); });
    const campo = el.querySelector<HTMLInputElement>("input[name=busca-redes]") as HTMLInputElement;
    campo.value = "kesia";
    campo.dispatchEvent(new Event("input"));
    const botao = el.querySelector<HTMLButtonElement>(".busca-redes-resultados button") as HTMLButtonElement;
    expect(botao.textContent).toContain("perfil indisponível");
    const antes = chamadas.filter((c) => c.startsWith("/api/redes/serie")).length;
    botao.click();
    const cartao = el.querySelector(".foco-cartao") as HTMLElement;
    expect(cartao.textContent).toContain("Perfil indisponível");
    expect(cartao.textContent).not.toMatch(/0 seguidores/);
    expect(cartao.querySelector("a[href*=divulgacandcontas]")).not.toBeNull();
    expect(el.querySelector(".serie-seguidores")?.textContent).toMatch(/Sem série/);
    expect(chamadas.filter((c) => c.startsWith("/api/redes/serie")).length).toBe(antes);
  });

  it("clique num ponto da nuvem seleciona o candidato como a busca e fixa o tooltip com link do perfil (T-W27)", async () => {
    const abertos: unknown[][] = [];
    simular(padrao());
    vi.stubGlobal("open", (...a: unknown[]) => { abertos.push(a); return null; });
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector('.grafico-redes-dispersao circle.marca[data-id="6"]')).not.toBeNull(); });
    const antes = chamadas.filter((c) => c.startsWith("/api/redes/serie")).length;
    const p = el.querySelector('.grafico-redes-dispersao circle.marca[data-id="6"]') as SVGElement;
    p.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: 100, clientY: 100 }));
    expect(abertos).toHaveLength(0);
    expect((el.querySelector("input[name=busca-redes]") as HTMLInputElement).value).toBe("Fábio Nunes");
    expect(el.querySelector(".foco-cartao")?.textContent).toContain("Fábio Nunes");
    expect(p.classList.contains("destaque")).toBe(true);
    expect(chamadas.filter((c) => c.startsWith("/api/redes/serie")).at(-1)).toContain("sq=6");
    expect(chamadas.filter((c) => c.startsWith("/api/redes/serie")).length).toBe(antes + 1);
    expect(el.querySelector(".grafico-redes-ritmo")?.textContent).toContain("Fábio Nunes");
    const balao = document.querySelector(".tooltip-flutuante.fixo:not([hidden])") as HTMLElement;
    expect(balao.textContent).toContain("Fábio Nunes");
    const a = balao.querySelector("a") as HTMLAnchorElement;
    expect(a.href).toBe("https://www.instagram.com/fabionunes_14/");
    expect(a.target).toBe("_blank");
    expect(a.rel).toBe("noopener noreferrer");
    expect(el.textContent).not.toContain("clique para abrir o perfil dele no Instagram");
    expect(el.textContent).toContain("clique para escolhê-lo como candidato em foco");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  });

  it("503 (dado ainda não publicado) vira aviso claro, não erro genérico", async () => {
    simular({ ...padrao(), "/api/redes": { status: 503, corpo: { detail: { codigo: "redes_indisponiveis" } } } });
    await desenhar();
    await vi.waitFor(() => { expect(el.querySelector(".estado.vazio")).not.toBeNull(); });
    expect(el.textContent).toContain("ainda não foram publicados");
    expect(el.querySelector(".estado.erro")).toBeNull();
  });
});
