import { describe, expect, it } from "vitest";
import type { Limites } from "../../src/componentes/mapa/geo";
import { LIMITES_UF, limitesDosIds } from "../../src/dados/limites-uf";

describe("LIMITES_UF", () => {
  it("cobre as 27 UFs com caixa válida", () => {
    expect(Object.keys(LIMITES_UF)).toHaveLength(27);
    for (const [oeste, sul, leste, norte] of Object.values(LIMITES_UF)) {
      expect(oeste).toBeLessThan(leste);
      expect(sul).toBeLessThan(norte);
    }
  });
});

describe("limitesDosIds", () => {
  it("município de SP (35…) enquadra só SP, independentemente de tiles carregados", () => {
    expect(limitesDosIds(["3550308", "3509502"])).toEqual(LIMITES_UF[35]);
  });
  it("zona usa o prefixo do município (id '2800308-12')", () => {
    expect(limitesDosIds(["2800308-12"])).toEqual(LIMITES_UF[28]);
  });
  it("várias UFs: união das caixas", () => {
    const [o, s, l, n] = limitesDosIds(["3550308", "2800308"]) ?? [];
    const sp = (LIMITES_UF[35] as Limites);
    const se = (LIMITES_UF[28] as Limites);
    expect([o, s, l, n]).toEqual([Math.min(sp[0], se[0]), Math.min(sp[1], se[1]), Math.max(sp[2], se[2]), Math.max(sp[3], se[3])]);
  });
  it("vazio ou UF desconhecida → null (sem chute)", () => {
    expect(limitesDosIds([])).toBeNull();
    expect(limitesDosIds(["9900000"])).toBeNull();
  });
});
