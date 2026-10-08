import { describe, expect, it } from "vitest";
import {
  ErroCoropleticoAbsoluto,
  escalaDivergente,
  escalaLimiar,
  escalaLog,
  escalaQuantil,
  expressaoCor,
  validarCoropletico,
  type MetaIndicador,
} from "../../src/componentes/escalas/escalas";
import { PALETAS } from "../../src/paletas";

const cem = Array.from({ length: 100 }, (_, i) => i + 1);

describe("escalaQuantil", () => {
  it("calcula quebras por quantis do conjunto", () => {
    const e = escalaQuantil(cem, PALETAS.sequencial.slice(0, 4));
    expect(e.quebras).toEqual([25.75, 50.5, 75.25]);
    expect(e.cor(1)).toBe(PALETAS.sequencial[0]);
    expect(e.cor(100)).toBe(PALETAS.sequencial[3]);
  });

  it("recusa quebras repetidas escondidas: remove duplicatas e reduz as classes", () => {
    const e = escalaQuantil([0, 0, 0, 0, 0, 0, 1, 2], PALETAS.sequencial.slice(0, 4));
    expect(new Set(e.quebras).size).toBe(e.quebras.length);
    expect(e.cores).toHaveLength(e.quebras.length + 1);
  });

  it("falha alto sem dados", () => {
    expect(() => escalaQuantil([], PALETAS.sequencial)).toThrow(/sem valores/i);
  });
});

describe("escalaLimiar — mesmas quebras em 2022 e 2026", () => {
  it("aplica as quebras de um conjunto a outro conjunto", () => {
    const base = escalaQuantil(cem, PALETAS.sequencial.slice(0, 4));
    const outra = escalaLimiar(base.quebras, base.cores);
    expect(outra.quebras).toEqual(base.quebras);
    expect([10, 30, 60, 90].map((v) => outra.cor(v))).toEqual([10, 30, 60, 90].map((v) => base.cor(v)));
    // 2026 com valores 3× maiores cai em classes mais altas com as MESMAS quebras
    expect(outra.classe(30 * 3)).toBeGreaterThan(outra.classe(30));
  });

  it("exige quebras estritamente crescentes e cores = quebras + 1", () => {
    expect(() => escalaLimiar([2, 1], ["#000", "#111", "#222"])).toThrow(/crescentes/);
    expect(() => escalaLimiar([1, 2], ["#000", "#111"])).toThrow(/cores/);
  });

  it("usa a classe a partir da quebra (limite inferior inclusivo, como step do MapLibre)", () => {
    const e = escalaLimiar([10], ["#aaaaaa", "#bbbbbb"]);
    expect(e.cor(9.999)).toBe("#aaaaaa");
    expect(e.cor(10)).toBe("#bbbbbb");
  });

  it("valor ausente recebe a cor de sem dado", () => {
    const e = escalaLimiar([10], ["#aaaaaa", "#bbbbbb"]);
    expect(e.cor(null)).toBe(e.corSemDado);
    expect(e.cor(undefined)).toBe(e.corSemDado);
    expect(e.cor(Number.NaN)).toBe(e.corSemDado);
  });
});

describe("escalaDivergente — swing centrado em 0", () => {
  const e = escalaDivergente({ extensao: 0.07 });
  it("quebras simétricas e classe neutra contendo o centro", () => {
    expect(e.centro).toBe(0);
    expect(e.quebras.map((q) => Number(q.toFixed(6)))).toEqual([-0.05, -0.03, -0.01, 0.01, 0.03, 0.05]);
    expect(e.cor(0)).toBe(PALETAS.divergente[3]);
    expect(e.cor(-0.2)).toBe(PALETAS.divergente[0]);
    expect(e.cor(0.2)).toBe(PALETAS.divergente[6]);
  });
});

describe("escalaLog — LQ centrado em 1", () => {
  const e = escalaLog({ fatorMaximo: 4 });
  it("quebras simétricas em log em torno de 1", () => {
    expect(e.centro).toBe(1);
    const n = e.quebras.length;
    for (let i = 0; i < n; i++) expect((e.quebras[i] ?? 0) * (e.quebras[n - 1 - i] ?? 0)).toBeCloseTo(1, 10);
    expect(e.cor(1)).toBe(PALETAS.divergente[3]);
    expect(e.cor(0.25)).toBe(PALETAS.divergente[0]);
    expect(e.cor(4)).toBe(PALETAS.divergente[6]);
    // LQ 2 e LQ 0,5 são equidistantes do neutro
    expect(Math.abs(e.classe(2) - 3)).toBe(Math.abs(e.classe(0.5) - 3));
  });

  it("rejeita fator máximo ≤ 1", () => {
    expect(() => escalaLog({ fatorMaximo: 1 })).toThrow();
  });
});

describe("expressaoCor — MapLibre", () => {
  it("gera step sobre o feature-state e cor para sem dado", () => {
    const e = escalaLimiar([10, 20], ["#aaaaaa", "#bbbbbb", "#cccccc"]);
    expect(expressaoCor(e)).toEqual([
      "case",
      ["!=", ["typeof", ["feature-state", "valor"]], "number"],
      e.corSemDado,
      ["step", ["feature-state", "valor"], "#aaaaaa", 10, "#bbbbbb", 20, "#cccccc"],
    ]);
  });

  it("aceita outra expressão de valor (propriedade do tile)", () => {
    const e = escalaLimiar([1], ["#aaaaaa", "#bbbbbb"]);
    const x = expressaoCor(e, ["get", "taxa"]) as unknown[];
    expect(JSON.stringify(x)).toContain('["get","taxa"]');
  });

  it("concorda com cor() em todas as classes", () => {
    const e = escalaQuantil(cem, PALETAS.sequencial);
    const expr = expressaoCor(e) as [string, unknown, string, [string, unknown, ...(string | number)[]]];
    const [, , ...resto] = expr[3];
    const cores = [resto[0], ...resto.filter((_, i) => i % 2 === 0 && i > 0)];
    expect(cores).toEqual([...e.cores]);
  });
});

describe("validarCoropletico", () => {
  const base: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "% dos votos válidos", denominador: "votos válidos do município" };

  it("aceita taxa, razão e diferença", () => {
    for (const tipo of ["taxa", "razao", "diferenca"] as const) expect(() => { validarCoropletico({ ...base, tipo }); }).not.toThrow();
  });

  it("recusa absoluto e sugere símbolos proporcionais", () => {
    expect(() => { validarCoropletico({ ...base, tipo: "absoluto" }); }).toThrow(ErroCoropleticoAbsoluto);
    expect(() => { validarCoropletico({ ...base, tipo: "absoluto" }); }).toThrow(/símbolos proporcionais/);
  });

  it("exige unidade e denominador", () => {
    expect(() => { validarCoropletico({ ...base, denominador: "" }); }).toThrow(/denominador/);
    expect(() => { validarCoropletico({ ...base, unidade: " " }); }).toThrow(/unidade/);
  });
});
