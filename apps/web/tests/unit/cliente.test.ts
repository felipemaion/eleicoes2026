import { afterEach, describe, expect, it, vi } from "vitest";
import { criarCliente } from "../../src/dados/cliente";

function simular(corpo: unknown, ok = true): void {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(corpo) })));
}
afterEach(() => { vi.unstubAllGlobals(); });

describe("cliente.meta", () => {
  it("aceita resposta válida", async () => {
    simular({ dt_geracao: "2026-10-07T10:00:00", fonte: "TSE" });
    await expect(criarCliente().meta()).resolves.toEqual({ dt_geracao: "2026-10-07T10:00:00", fonte: "TSE" });
  });
  it("aceita dt_geracao nulo", async () => {
    simular({ dt_geracao: null, fonte: "TSE" });
    await expect(criarCliente().meta()).resolves.toMatchObject({ dt_geracao: null });
  });
  it("rejeita formato inesperado em vez de repassar", async () => {
    simular({ fonte: 3 });
    await expect(criarCliente().meta()).rejects.toThrow(/inesperada/);
    simular(null);
    await expect(criarCliente().meta()).rejects.toThrow(/inesperada/);
  });
});
