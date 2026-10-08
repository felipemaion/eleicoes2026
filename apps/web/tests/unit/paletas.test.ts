import { describe, expect, it } from "vitest";
import { contraste, cssDasCores, luminancia, OFICIAL_MISSAO, PALETAS, TEMAS } from "../../src/paletas";

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

  it("cor de 'sem dado' é token de tema, distinguível do fundo, da superfície e da classe mais clara", () => {
    for (const t of Object.values(TEMAS)) {
      expect(contraste(t.semDado, t.fundo)).toBeGreaterThanOrEqual(1.5);
      expect(contraste(t.semDado, t.superficie)).toBeGreaterThanOrEqual(1.2);
    }
    expect(contraste(TEMAS.claro.semDado, PALETAS.sequencial[0])).toBeGreaterThanOrEqual(1.3);
    expect(contraste(TEMAS.escuro.semDado, PALETAS.sequencial[0])).toBeGreaterThanOrEqual(1.3);
    expect(TEMAS.claro.semDado).not.toBe(TEMAS.escuro.semDado);
  });

  it("identidade Missão: preto/amarelo oficiais, tema escuro por padrão", () => {
    expect(OFICIAL_MISSAO.preto).toBe("#070d0c");
    expect(OFICIAL_MISSAO.amarelo).toBe("#fcbe26");
    expect(TEMAS.escuro.fundo).toBe(OFICIAL_MISSAO.preto);
    expect(TEMAS.escuro.acento).toBe(OFICIAL_MISSAO.amarelo);
    expect(cssDasCores()).toMatch(/^:root\{[^}]*--cor-fundo:#070d0c/);
  });

  it("amarelo nunca é texto sobre branco: no tema claro o destaque tem ≥ 4.5:1 com o fundo", () => {
    expect(contraste(TEMAS.claro.destaque, TEMAS.claro.fundo)).toBeGreaterThanOrEqual(4.5);
    expect(contraste(TEMAS.escuro.destaque, TEMAS.escuro.fundo)).toBeGreaterThanOrEqual(4.5);
    for (const t of Object.values(TEMAS)) {
      expect(contraste(t.textoAcento, t.acento)).toBeGreaterThanOrEqual(7);
      expect(contraste(t.dado, t.fundo)).toBeGreaterThanOrEqual(3);
      expect(contraste(t.dado, t.superficie)).toBeGreaterThanOrEqual(3);
    }
  });

  it("sequencial vai do claro ao escuro e é visível sobre a superfície do mapa nos dois temas", () => {
    const s = PALETAS.sequencial;
    for (let i = 1; i < s.length; i++) expect(luminancia(s[i] as string)).toBeLessThan(luminancia(s[i - 1] as string));
    // No tema claro a classe mais clara fica próxima do fundo do mapa: as bordas dos polígonos fazem a separação.
    for (const cor of s) expect(contraste(cor, TEMAS.escuro.superficie)).toBeGreaterThanOrEqual(1.5);
  });

  it("contraste calcula valores de referência", () => {
    expect(contraste("#000000", "#ffffff")).toBeCloseTo(21, 0);
  });
});
