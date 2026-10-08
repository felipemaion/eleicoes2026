import { describe, expect, it } from "vitest";
import { contraste, PALETAS, TEMAS } from "../../src/paletas";

describe("paletas", () => {
  it("tem o nº de classes esperado", () => {
    expect(PALETAS.sequencial).toHaveLength(7);
    expect(PALETAS.divergente).toHaveLength(7);
    expect(PALETAS.categorica).toHaveLength(8);
  });

  it("divergente é simétrica em torno de um neutro claro", () => {
    const d = PALETAS.divergente;
    // neutro claro: contraste com branco < 1.2 (quase branco)
    expect(contraste(d[3], "#ffffff")).toBeLessThan(1.2);
    // extremos distinguíveis do neutro nos dois lados (PuOr não é simétrica em luminância)
    expect(contraste(d[0], d[3])).toBeGreaterThan(3);
    expect(contraste(d[6], d[3])).toBeGreaterThan(3);
    // degraus se afastam do neutro de forma monotônica nos dois lados
    expect(contraste(d[2], d[3])).toBeLessThan(contraste(d[1], d[3]));
    expect(contraste(d[1], d[3])).toBeLessThan(contraste(d[0], d[3]));
    expect(contraste(d[4], d[3])).toBeLessThan(contraste(d[5], d[3]));
    expect(contraste(d[5], d[3])).toBeLessThan(contraste(d[6], d[3]));
  });

  it("cores são únicas dentro de cada paleta", () => {
    for (const p of Object.values(PALETAS)) expect(new Set(p).size).toBe(p.length);
  });

  it("contraste do texto ≥ 4.5:1 (AA) nos dois temas", () => {
    for (const t of Object.values(TEMAS)) {
      expect(contraste(t.texto, t.fundo)).toBeGreaterThanOrEqual(4.5);
      expect(contraste(t.textoSuave, t.fundo)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("contraste calcula valores de referência", () => {
    expect(contraste("#000000", "#ffffff")).toBeCloseTo(21, 0);
  });
});
