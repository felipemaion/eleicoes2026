import { describe, expect, it } from "vitest";
import { posicionar } from "../../src/componentes/ui/posicionamento";

const vp = { largura: 1000, altura: 700 };
const caixa = { largura: 200, altura: 100 };

describe("posicionar tooltip", () => {
  it("abre abaixo da âncora quando cabe, centralizado", () => {
    const p = posicionar({ x: 400, y: 100, largura: 40, altura: 20 }, caixa, vp);
    expect(p.lado).toBe("baixo");
    expect(p.x).toBe(320);
    expect(p.y).toBeGreaterThan(120);
  });
  it("vira para cima quando não cabe embaixo", () => {
    const p = posicionar({ x: 400, y: 640, largura: 40, altura: 20 }, caixa, vp);
    expect(p.lado).toBe("cima");
    expect(p.y + caixa.altura).toBeLessThanOrEqual(640);
  });
  it("nunca sai da tela nas bordas e a seta continua apontando para a âncora", () => {
    const esq = posicionar({ x: 0, y: 100, largura: 20, altura: 20 }, caixa, vp);
    expect(esq.x).toBeGreaterThanOrEqual(8);
    expect(esq.seta).toBeGreaterThanOrEqual(8);
    const dir = posicionar({ x: 990, y: 100, largura: 10, altura: 20 }, caixa, vp);
    expect(dir.x + caixa.largura).toBeLessThanOrEqual(vp.largura - 8);
    expect(dir.x + dir.seta).toBeGreaterThan(960);
  });
  it("caixa maior que a tela é encolhida para caber via largura máxima", () => {
    const p = posicionar({ x: 10, y: 10, largura: 10, altura: 10 }, { largura: 2000, altura: 100 }, vp);
    expect(p.largura).toBeLessThanOrEqual(vp.largura - 16);
  });
  it("ponto no canto superior direito: caixa inteira dentro da viewport, sem encolher", () => {
    const p = posicionar({ x: 995, y: 4, largura: 0, altura: 0 }, { largura: 340, altura: 260 }, vp);
    expect(p.largura).toBe(340);
    expect(p.x).toBeGreaterThanOrEqual(8);
    expect(p.x + p.largura).toBeLessThanOrEqual(vp.largura - 8);
    expect(p.y).toBeGreaterThanOrEqual(8);
    expect(p.y + 260).toBeLessThanOrEqual(vp.altura - 8);
  });
  it("ponto na borda inferior: vira para cima, dentro da tela", () => {
    const p = posicionar({ x: 500, y: 695, largura: 0, altura: 0 }, caixa, vp);
    expect(p.lado).toBe("cima");
    expect(p.y).toBeGreaterThanOrEqual(8);
  });
  it("sem espaço acima nem abaixo, usa o lado com mais espaço, sem cobrir a âncora", () => {
    const alta = { largura: 300, altura: 650 };
    const dir = posicionar({ x: 100, y: 350, largura: 0, altura: 0 }, alta, vp);
    expect(dir.lado).toBe("direita");
    expect(dir.x).toBeGreaterThan(100);
    expect(dir.y).toBeGreaterThanOrEqual(8);
    expect(dir.y + alta.altura).toBeLessThanOrEqual(vp.altura - 8);
    const esq = posicionar({ x: 900, y: 350, largura: 0, altura: 0 }, alta, vp);
    expect(esq.lado).toBe("esquerda");
    expect(esq.x + alta.largura).toBeLessThan(900);
  });
  it("só encolhe quando a largura natural excede a tela e sinaliza", () => {
    expect(posicionar({ x: 10, y: 10, largura: 0, altura: 0 }, { largura: 2000, altura: 100 }, vp).comprimida).toBe(true);
    expect(posicionar({ x: 10, y: 10, largura: 0, altura: 0 }, caixa, vp).comprimida).toBe(false);
  });
});
