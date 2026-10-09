import { describe, expect, it } from "vitest";
import { proximoIndiceDeFoco } from "../../src/componentes/ui/cabecalho-movel";

describe("proximoIndiceDeFoco", () => {
  it("avança e volta ao início no fim", () => {
    expect(proximoIndiceDeFoco(0, 3, false)).toBe(1);
    expect(proximoIndiceDeFoco(2, 3, false)).toBe(0);
  });
  it("Shift+Tab recua e dá a volta no começo", () => {
    expect(proximoIndiceDeFoco(2, 3, true)).toBe(1);
    expect(proximoIndiceDeFoco(0, 3, true)).toBe(2);
  });
  it("foco fora da lista entra pelo primeiro/último; lista vazia não move", () => {
    expect(proximoIndiceDeFoco(-1, 3, false)).toBe(0);
    expect(proximoIndiceDeFoco(-1, 3, true)).toBe(2);
    expect(proximoIndiceDeFoco(0, 0, false)).toBe(-1);
  });
});
