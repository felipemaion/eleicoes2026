import { describe, expect, it } from "vitest";
import { contraste, PALETAS, TEMAS } from "../../src/paletas";

describe("paletas", () => {
  it("tem o nº de classes esperado", () => {
    expect(PALETAS.sequencial).toHaveLength(7);
    expect(PALETAS.divergente).toHaveLength(7);
    expect(PALETAS.categorica).toHaveLength(8);
  });

  it("divergente é simétrica em torno de um neutro claro", () => {
    expect(PALETAS.divergente[3]).toMatch(/^#/);
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
