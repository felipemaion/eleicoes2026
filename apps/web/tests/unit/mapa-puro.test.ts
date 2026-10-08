import { describe, expect, it } from "vitest";
import { limitesDe } from "../../src/componentes/mapa/geo";
import { expressaoRaioCirculo, expressaoPesoCalor, soFinitos } from "../../src/componentes/mapa/expressoes";
import { textoTooltip } from "../../src/componentes/mapa/tooltip";

describe("limitesDe", () => {
  it("calcula bbox de Polygon e MultiPolygon", () => {
    const b = limitesDe({
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[-37, -11], [-36, -11], [-36, -10], [-37, -11]]] } },
        { type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: [[[[-38, -9], [-35, -9], [-35, -12], [-38, -9]]]] } },
      ],
    });
    expect(b).toEqual([-38, -12, -35, -9]);
  });
  it("falha alto sem geometria", () => {
    expect(() => limitesDe({ type: "FeatureCollection", features: [] })).toThrow(/vazia/);
  });
});

describe("expressões de densidade", () => {
  it("raio proporcional a √votos, com teto no maior ponto", () => {
    const x = expressaoRaioCirculo(10000, 20) as [string, number, unknown];
    expect(x[0]).toBe("*");
    expect(x[1]).toBeCloseTo(20 / 100, 10);
    expect(x[2]).toEqual(["sqrt", ["max", 0, ["to-number", ["get", "votos"], 0]]]);
  });
  it("peso do calor normalizado em [0,1]", () => {
    expect(expressaoPesoCalor(500)).toEqual(["min", 1, ["/", ["to-number", ["get", "votos"], 0], 500]]);
  });
  it("recusa votos máximos ≤ 0", () => {
    expect(() => expressaoRaioCirculo(0, 20)).toThrow();
  });
});

describe("textoTooltip", () => {
  it("traz absoluto, taxa e eleitorado em pt-BR", () => {
    const t = textoTooltip({ nome: "Aracaju", votos: 12345, taxa: 0.0456, eleitorado: 400000 }, { unidade: "% dos votos válidos", formatarTaxa: (v) => `${(v * 100).toFixed(1).replace(".", ",")}%` });
    expect(t.titulo).toBe("Aracaju");
    expect(t.linhas).toEqual([
      ["Votos", "12.345"],
      ["Taxa (% dos votos válidos)", "4,6%"],
      ["Eleitorado", "400.000"],
    ]);
  });
  it("mostra 'sem dado' em vez de zero quando falta valor", () => {
    const t = textoTooltip({ nome: "X" }, { unidade: "u", formatarTaxa: String });
    expect(t.linhas.map((l) => l[1])).toEqual(["sem dado", "sem dado", "sem dado"]);
  });
});

describe("soFinitos", () => {
  it("descarta NaN e ±Infinity, mantém zero e negativos", () => {
    expect(soFinitos({ a: 0, b: Number.NaN, c: Infinity, d: -Infinity, e: -1.5 })).toEqual({ a: 0, e: -1.5 });
  });
});
