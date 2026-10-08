import { describe, expect, it } from "vitest";
import { marcarNBaixo } from "../../src/dados/n-baixo";
import { textoTooltip } from "../../src/componentes/mapa/tooltip";

const fmt = (v: number): string => String(v);

describe("marcarNBaixo (spec §1.4: E = aptos × taxa da UF < 20)", () => {
  it("marca quem tem menos de 20 votos esperados, pela taxa da própria UF", () => {
    // UF 28: 1.000 votos em 100.000 aptos → taxa 1%. Grande: E=900; pequeno: E=0,5.
    const r = marcarNBaixo({
      "2800001": { votos: 900, eleitorado: 90_000 },
      "2800002": { votos: 100, eleitorado: 9_950 },
      "2800003": { votos: 0, eleitorado: 50 },
    });
    expect(r).toEqual({ "2800001": false, "2800002": false, "2800003": true });
  });

  it("o limiar é estrito: E = 20 não é n baixo", () => {
    const r = marcarNBaixo({ "2800001": { votos: 20, eleitorado: 2_000 }, "2800002": { votos: 0, eleitorado: 0 } });
    // taxa UF = 20/2000 = 1%; E(001)=20 → não é baixo; aptos=0 → sempre baixo.
    expect(r).toEqual({ "2800001": false, "2800002": true });
  });

  it("cada UF usa a sua taxa (2 primeiros dígitos do IBGE), inclusive em chave de zona", () => {
    const r = marcarNBaixo({
      "2800001-5": { votos: 500, eleitorado: 10_000 }, // UF 28: taxa 5% → E=500
      "3500001-9": { votos: 1, eleitorado: 10_000 }, // UF 35: taxa 0,01% → E=1
    });
    expect(r).toEqual({ "2800001-5": false, "3500001-9": true });
  });

  it("sem votos na UF inteira, todos são n baixo (nada esperado)", () => {
    expect(marcarNBaixo({ "2800001": { votos: 0, eleitorado: 1_000_000 } })).toEqual({ "2800001": true });
  });
});

describe("tooltip e n baixo", () => {
  it("acrescenta a linha de confiabilidade só quando n_baixo", () => {
    const o = { unidade: "‰", formatarTaxa: fmt };
    expect(textoTooltip({ nome: "A", votos: 1, taxa: 1, eleitorado: 10, nBaixo: true }, o).linhas.at(-1)).toEqual(["Estimativa", "instável (menos de 20 votos esperados)"]);
    expect(textoTooltip({ nome: "A", votos: 1, taxa: 1, eleitorado: 10, nBaixo: false }, o).linhas).toHaveLength(3);
  });
});
