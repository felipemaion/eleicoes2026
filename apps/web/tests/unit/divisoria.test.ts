import { describe, expect, it } from "vitest";
import { larguraPorTecla, limitarLargura, PASSO_TECLADO, PASSO_TECLADO_GRANDE } from "../../src/componentes/ui/divisoria";

describe("limitarLargura", () => {
  it("mantém dentro dos limites e arredonda", () => {
    expect(limitarLargura(300.4, 240, 600)).toBe(300);
    expect(limitarLargura(100, 240, 600)).toBe(240);
    expect(limitarLargura(900, 240, 600)).toBe(600);
  });
  it("com limites cruzados (tela apertada) vale o mínimo", () => {
    expect(limitarLargura(500, 240, 200)).toBe(240);
  });
});

describe("larguraPorTecla", () => {
  it("← aumenta o painel e → diminui, em passos", () => {
    expect(larguraPorTecla("ArrowLeft", 300, 240, 600)).toBe(300 + PASSO_TECLADO);
    expect(larguraPorTecla("ArrowRight", 300, 240, 600)).toBe(300 - PASSO_TECLADO);
    expect(larguraPorTecla("ArrowLeft", 300, 240, 600, true)).toBe(300 + PASSO_TECLADO_GRANDE);
  });
  it("respeita os limites", () => {
    expect(larguraPorTecla("ArrowRight", 245, 240, 600)).toBe(240);
    expect(larguraPorTecla("ArrowLeft", 595, 240, 600)).toBe(600);
  });
  it("Home vai ao mínimo e End ao máximo do painel", () => {
    expect(larguraPorTecla("Home", 300, 240, 600)).toBe(240);
    expect(larguraPorTecla("End", 300, 240, 600)).toBe(600);
  });
  it("outras teclas não são da divisória", () => {
    expect(larguraPorTecla("a", 300, 240, 600)).toBeNull();
  });
});
