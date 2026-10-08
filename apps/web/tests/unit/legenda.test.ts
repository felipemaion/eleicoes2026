import { describe, expect, it } from "vitest";
import { escalaLimiar, type MetaIndicador } from "../../src/componentes/escalas/escalas";
import { criarLegenda } from "../../src/componentes/escalas/legenda";

const meta: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "% dos votos válidos", denominador: "votos válidos do município" };
const e = escalaLimiar([0.01, 0.05], ["#eff3ff", "#6baed6", "#084594"]);

describe("criarLegenda", () => {
  it("mostra unidade e denominador sempre", () => {
    const svg = criarLegenda(e, meta, { formatar: (v) => `${(v * 100).toFixed(0)}%` });
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg.getAttribute("role")).toBe("img");
    const texto = svg.textContent;
    expect(texto).toContain("% dos votos válidos");
    expect(texto).toContain("votos válidos do município");
  });

  it("tem um bloco por classe, um para sem dado e rótulos nas quebras", () => {
    const svg = criarLegenda(e, meta, { formatar: (v) => `${(v * 100).toFixed(0)}%` });
    expect(svg.querySelectorAll("rect.classe")).toHaveLength(3);
    expect(svg.querySelectorAll("rect.sem-dado")).toHaveLength(1);
    expect([...svg.querySelectorAll("text.quebra")].map((t) => t.textContent)).toEqual(["1%", "5%"]);
  });

  it("descrição acessível lista as faixas", () => {
    const svg = criarLegenda(e, meta, { formatar: (v) => String(v) });
    expect(svg.querySelector("title")?.textContent).toMatch(/Penetração/);
    expect(svg.querySelector("desc")?.textContent).toMatch(/0,01|0.01/);
  });

  it("recusa meta absoluta", () => {
    expect(() => criarLegenda(e, { ...meta, tipo: "absoluto" })).toThrow(/símbolos proporcionais/);
  });
});
