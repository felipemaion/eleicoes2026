import { afterEach, describe, expect, it, vi } from "vitest";
import { carregarManifesto, fontesDoManifesto, lerManifesto } from "../../src/dados/tiles";

const MANIFESTO = {
  camadas: {
    municipios: { arquivo: "municipios.a1b2c3.pmtiles", camada: "municipios", id: "cd_mun_ibge", limites: [-74, -34, -34, 5] },
    zonas_2026: { arquivo: "zonas_2026.d4e5f6.pmtiles", camada: "zonas", id: "id_zona", limites: [-74, -34, -34, 5] },
  },
};
afterEach(() => { vi.unstubAllGlobals(); });

describe("lerManifesto", () => {
  it("aceita o formato publicado pelo ETL", () => {
    expect(lerManifesto(MANIFESTO).camadas["municipios"]?.arquivo).toBe("municipios.a1b2c3.pmtiles");
  });
  it("falha alto quando falta a camada de municípios", () => {
    expect(() => lerManifesto({ camadas: {} })).toThrow(/municipios/);
  });
  it("falha alto em camada malformada (limites)", () => {
    const ruim = { camadas: { municipios: { ...MANIFESTO.camadas.municipios, limites: [1, 2] } } };
    expect(() => lerManifesto(ruim)).toThrow(/limites/);
    expect(() => lerManifesto(null)).toThrow();
  });
});

describe("fontesDoManifesto", () => {
  const m = lerManifesto(MANIFESTO);
  it("município sempre; zona só se existe a camada do ano", () => {
    const f2026 = fontesDoManifesto(m, 2026, "https://x.org");
    expect(f2026.municipio).toMatchObject({ tipo: "pmtiles", url: "https://x.org/tiles/municipios.a1b2c3.pmtiles", camadaFonte: "municipios", idPropriedade: "cd_mun_ibge" });
    expect(f2026.zona).toMatchObject({ url: "https://x.org/tiles/zonas_2026.d4e5f6.pmtiles", camadaFonte: "zonas", idPropriedade: "id_zona" });
    expect(fontesDoManifesto(m, 2022, "https://x.org").zona).toBeUndefined();
  });
});

describe("carregarManifesto", () => {
  it("404 = ainda não há tiles (null); outro erro falha alto", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })));
    await expect(carregarManifesto()).resolves.toBeNull();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    await expect(carregarManifesto()).rejects.toThrow(/500/);
  });
  it("lê e valida; pede com cache desligado (o nome tem hash, o manifesto não)", async () => {
    const f = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(MANIFESTO) }));
    vi.stubGlobal("fetch", f);
    await expect(carregarManifesto()).resolves.toMatchObject({ camadas: { municipios: { camada: "municipios" } } });
    expect(f).toHaveBeenCalledWith("/tiles/manifesto.json", { cache: "no-cache" });
  });
});
