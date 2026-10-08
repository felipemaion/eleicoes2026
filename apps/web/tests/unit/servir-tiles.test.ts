import { describe, expect, it } from "vitest";
import { caminhoSeguro, lerRange } from "../../servir-tiles";

describe("caminhoSeguro", () => {
  it("resolve dentro da raiz e recusa travessia de diretório", () => {
    expect(caminhoSeguro("/dados/tiles", "/tiles/municipios.ab12.pmtiles")).toBe("/dados/tiles/municipios.ab12.pmtiles");
    expect(caminhoSeguro("/dados/tiles", "/tiles/../../etc/passwd")).toBeNull();
    expect(caminhoSeguro("/dados/tiles", "/tiles/%2e%2e/segredo")).toBeNull();
    expect(caminhoSeguro("/dados/tiles", "/api/meta")).toBeNull();
  });
});

describe("lerRange", () => {
  it("bytes=a-b, aberto no fim e sufixo", () => {
    expect(lerRange("bytes=0-99", 1000)).toEqual({ inicio: 0, fim: 99 });
    expect(lerRange("bytes=900-", 1000)).toEqual({ inicio: 900, fim: 999 });
    expect(lerRange("bytes=-100", 1000)).toEqual({ inicio: 900, fim: 999 });
    expect(lerRange("bytes=0-5000", 1000)).toEqual({ inicio: 0, fim: 999 });
  });
  it("sem cabeçalho = arquivo inteiro (null); fora do arquivo = inválido", () => {
    expect(lerRange(undefined, 1000)).toBeNull();
    expect(lerRange("bytes=2000-3000", 1000)).toBe("invalido");
    expect(lerRange("bytes=abc", 1000)).toBe("invalido");
  });
});
