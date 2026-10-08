import { describe, expect, it, vi } from "vitest";
import { criarStore, FILTROS_PADRAO } from "../../src/store";
import { formatarHash, lerHash, ligarStoreAoHash } from "../../src/rotas";

describe("store", () => {
  it("notifica assinantes ao mudar filtro e ignora mudança nula", () => {
    const store = criarStore();
    const ouvinte = vi.fn();
    store.assinar(ouvinte);
    store.definir({ uf: "SP" });
    store.definir({ uf: "SP" });
    expect(ouvinte).toHaveBeenCalledTimes(1);
    expect(store.obter().filtros.uf).toBe("SP");
  });
});

describe("hash", () => {
  it("formata só o que difere do padrão", () => {
    expect(formatarHash("mapa", FILTROS_PADRAO)).toBe("#/mapa");
    expect(formatarHash("mapa", { ...FILTROS_PADRAO, uf: "SP", ano: 2022 })).toBe("#/mapa?uf=SP&ano=2022");
  });

  it("lê tela e filtros; valores inválidos caem no padrão", () => {
    expect(lerHash("#/gastos?uf=MG&cargo=deputado_federal")).toEqual({
      tela: "gastos",
      filtros: { ...FILTROS_PADRAO, uf: "MG", cargo: "deputado_federal" },
    });
    expect(lerHash("#/xyz?uf=ZZ&ano=1999")).toEqual({ tela: "visao-geral", filtros: FILTROS_PADRAO });
    expect(lerHash("")).toEqual({ tela: "visao-geral", filtros: FILTROS_PADRAO });
  });

  it("mudar filtro atualiza a URL e mudar a URL atualiza o store", () => {
    const store = criarStore();
    const desligar = ligarStoreAoHash(store, window);
    store.definir({ uf: "RJ" });
    expect(window.location.hash).toBe("#/visao-geral?uf=RJ");
    window.location.hash = "#/evolucao?uf=PR&ano=2022";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect(store.obter().tela).toBe("evolucao");
    expect(store.obter().filtros).toMatchObject({ uf: "PR", ano: 2022 });
    desligar();
  });
});
