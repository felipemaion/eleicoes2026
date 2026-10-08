import { describe, expect, it } from "vitest";
import { CODIGO_UF, limitesDaAbrangencia, paramsMapaDoCandidato, textoForaDoMapa } from "../../src/dados/abrangencia";
import { expressaoOpacidade } from "../../src/componentes/mapa/expressoes";
import { UFS } from "../../src/store";

describe("abrangência do candidato", () => {
  it("todas as UFs têm código IBGE de 2 dígitos", () => {
    for (const u of UFS) expect(CODIGO_UF[u]).toMatch(/^\d{2}$/);
    expect(CODIGO_UF["SE"]).toBe("28");
  });
  it("presidente enquadra o país (sem limites) e UF enquadra a caixa da UF", () => {
    expect(limitesDaAbrangencia({ tipo: "pais", uf: null })).toBeNull();
    expect(limitesDaAbrangencia({ tipo: "uf", uf: "SE" })).toEqual([-38.2383, -11.5624, -36.3959, -9.515]);
  });
  it("params do mapa vêm do candidato, nunca dos filtros da tela", () => {
    const base = { ano: 2026, sq_candidato: 280002540694, cargo: "PRESIDENTE" };
    expect(paramsMapaDoCandidato({ ...base, abrangencia: { tipo: "pais", uf: null } })).toEqual({
      ano: "2026", cargo: "PRESIDENTE", sq_candidato: "280002540694", indicador: "penetracao", nivel: "municipio",
    });
    expect(paramsMapaDoCandidato({ ...base, cargo: "SENADOR", abrangencia: { tipo: "uf", uf: "MS" } })).toMatchObject({ cargo: "SENADOR", uf: "MS" });
  });
  it("votos fora do mapa viram texto próprio, só quando existem", () => {
    expect(textoForaDoMapa(0)).toBeNull();
    expect(textoForaDoMapa(8580)).toBe("Votos no exterior: 8.580 (fora do mapa).");
  });
});

describe("expressão de opacidade por abrangência", () => {
  it("sem UF todas as áreas ficam com a opacidade cheia", () => {
    expect(expressaoOpacidade("cd_mun_ibge", null, 0.9, 0.1)).toBe(0.9);
  });
  it("com UF esmaece as áreas cujo código não começa pelo da UF", () => {
    expect(expressaoOpacidade("cd_mun_ibge", "28", 0.9, 0.1)).toEqual([
      "case", ["==", ["slice", ["to-string", ["get", "cd_mun_ibge"]], 0, 2], "28"], 0.9, 0.1,
    ]);
  });
});
