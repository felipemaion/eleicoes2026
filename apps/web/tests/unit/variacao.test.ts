import { beforeEach, describe, expect, it } from "vitest";
import { formatarVariacao } from "../../src/formato";
import * as serie from "../../src/componentes/graficos/serie-tempo";

describe("formatarVariacao (T-W29)", () => {
  it("positivo com sinal, milhar com ponto e % com 1 casa", () => {
    expect(formatarVariacao({ abs: 1234, pct: 2.1, dias: 1 })).toBe("+1.234 (+2,1%)");
  });
  it("negativo usa o sinal de menos tipográfico", () => {
    expect(formatarVariacao({ abs: -340, pct: -0.65, dias: 1 })).toBe("−340 (−0,7%)");
  });
  it("zero = 0 (0,0%), sem sinal", () => {
    expect(formatarVariacao({ abs: 0, pct: 0, dias: 1 })).toBe("0 (0,0%)");
  });
  it("sem delta_abs (1º ponto) → null; sem pct mostra só o absoluto", () => {
    expect(formatarVariacao({ abs: null, pct: null, dias: null })).toBeNull();
    expect(formatarVariacao({ abs: 50, pct: null, dias: 1 })).toBe("+50");
  });
  it("pct que arredonda para 0,0 não leva sinal (T-W30)", () => {
    expect(formatarVariacao({ abs: 5, pct: 0.04, dias: 1 })).toBe("+5 (0,0%)");
    expect(formatarVariacao({ abs: -5, pct: -0.04, dias: 1 })).toBe("−5 (0,0%)");
  });
  it("dias null não vira '1 dia' em silêncio: declara o intervalo desconhecido (T-W30)", () => {
    expect(formatarVariacao({ abs: 7, pct: 1, dias: null })).toBe("+7 (+1,0%) em intervalo não informado");
  });
  it("dias > 1 diz o intervalo (coleta faltou), nunca interpola", () => {
    expect(formatarVariacao({ abs: 2010, pct: 3.4, dias: 3 })).toBe("+2.010 (+3,4%) em 3 dias");
    expect(formatarVariacao({ abs: 2010, pct: 3.4, dias: 2.96 })).toBe("+2.010 (+3,4%) em 3 dias");
    expect(formatarVariacao({ abs: 10, pct: 1, dias: 1.2 })).toBe("+10 (+1,0%)");
  });
});

let el: HTMLElement;
beforeEach(() => { document.body.innerHTML = '<div id="c"></div>'; el = document.getElementById("c") as HTMLElement; });

const ponto = (i: number, valor: number, abs: number | null, pct: number | null, dias: number | null) => ({
  quando: new Date(Date.UTC(2026, 9, 1 + i, 12)).toISOString(), valor, variacao: { abs, pct, dias },
});
const tres = [ponto(0, 1000, null, null, null), ponto(1, 1100, 100, 10, 1), ponto(2, 1050, -50, -4.5, 1)];

const hover = (seg: Element | undefined): string => {
  seg?.dispatchEvent(new MouseEvent("mouseenter", { clientX: 100, clientY: 100 }));
  return document.body.textContent;
};

describe("série de tempo: variação só no hover do segmento (T-W30)", () => {
  it("nenhum rótulo fixo: nem texto de variação no SVG sem hover", () => {
    serie.render(el, tres, { titulo: "S", medida: "Seguidores" });
    expect(el.querySelectorAll("text.variacao-trecho")).toHaveLength(0);
    expect(el.querySelector("svg")?.textContent).not.toContain("+100 (+10,0%)");
  });
  it("todo trecho tem área de captura invisível e mais grossa, entre os dois pontos", () => {
    serie.render(el, tres, { titulo: "S", medida: "Seguidores" });
    const caps = [...el.querySelectorAll("line.trecho-captura")];
    expect(caps).toHaveLength(2);
    const m = [...el.querySelectorAll("circle.marca")].map((c) => Number(c.getAttribute("cx")));
    expect(Number(caps[0]?.getAttribute("x1"))).toBeCloseTo(m[0] ?? 0, 1);
    expect(Number(caps[0]?.getAttribute("x2"))).toBeCloseTo(m[1] ?? 0, 1);
    expect(Number(caps[1]?.getAttribute("x2"))).toBeCloseTo(m[2] ?? 0, 1);
    expect(Number(caps[0]?.getAttribute("stroke-width"))).toBeGreaterThanOrEqual(12);
    expect(caps[0]?.getAttribute("stroke")).toBe("transparent");
  });
  it("hover em cada segmento mostra a variação certa com as duas datas; sair esconde e desrealça", () => {
    serie.render(el, tres, { titulo: "S", medida: "Seguidores" });
    const caps = [...el.querySelectorAll("line.trecho-captura")];
    expect(hover(caps[0])).toContain("01/10 → 02/10");
    expect(document.body.textContent).toContain("+100 (+10,0%)");
    expect(el.querySelectorAll("line.trecho-realce.ativo")).toHaveLength(1);
    caps[0]?.dispatchEvent(new MouseEvent("mouseleave"));
    expect(el.querySelectorAll("line.trecho-realce.ativo")).toHaveLength(0);
    expect(hover(caps[1])).toContain("02/10 → 03/10");
    expect(document.body.textContent).toContain("−50 (−4,5%)");
  });
  it("sem regra de omitir: série densa também tem todos os trechos", () => {
    const muitos = Array.from({ length: 40 }, (_, i) => ponto(i, 1000 + i * 7, i === 0 ? null : 7, i === 0 ? null : 0.7, i === 0 ? null : 1));
    serie.render(el, muitos, { titulo: "S", medida: "Seguidores", largura: 400 });
    expect(el.querySelectorAll("line.trecho-captura")).toHaveLength(39);
    expect(el.querySelectorAll("circle.marca")).toHaveLength(40);
  });
  it("trecho com dias > 1 diz o intervalo no balão", () => {
    serie.render(el, [ponto(0, 1000, null, null, null), ponto(3, 3010, 2010, 3.4, 3)], { titulo: "S", medida: "Seguidores" });
    hover(el.querySelector("line.trecho-captura") ?? undefined);
    expect(document.body.textContent).toContain("+2.010 (+3,4%) em 3 dias");
  });
  it("tooltip do ponto e tabela alternativa mostram a variação", () => {
    serie.render(el, tres, { titulo: "S", medida: "Seguidores" });
    const c2 = el.querySelectorAll("circle.marca")[1];
    expect(c2?.getAttribute("aria-label")).toContain("+100 (+10,0%)");
    expect((c2 as SVGElement).dataset["tooltip"]).toContain("+100 (+10,0%)");
    const ths = [...el.querySelectorAll("details thead th")].map((t) => t.textContent);
    expect(ths).toEqual(["Coleta", "Seguidores", "Variação"]);
    const linhas = [...el.querySelectorAll("details tbody tr")].map((r) => r.lastElementChild?.textContent);
    expect(linhas).toEqual(["—", "+100 (+10,0%)", "−50 (−4,5%)"]);
  });
  it("sem `variacao` nos pontos (outros usos) nada muda: sem trechos nem coluna extra", () => {
    serie.render(el, tres.map(({ quando, valor }) => ({ quando, valor })), { titulo: "S", medida: "Seguidores" });
    expect(el.querySelectorAll("line.trecho-captura")).toHaveLength(0);
    expect([...el.querySelectorAll("details thead th")].map((t) => t.textContent)).toEqual(["Coleta", "Seguidores"]);
  });
});
