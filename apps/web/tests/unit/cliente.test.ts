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

describe("cliente — endpoints de domínio", () => {
  function espiar(corpo: unknown): ReturnType<typeof vi.fn> {
    const f = vi.fn((_url: string) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(corpo) }));
    vi.stubGlobal("fetch", f);
    return f;
  }
  it("monta a URL com query só dos parâmetros presentes", async () => {
    const f = espiar({ valores: {}, detalhes: {}, escala_sugerida: "quantil", tipo: "taxa", unidade: "u", denominador: "d" });
    await criarCliente("/api").mapa({ ano: "2026", uf: "SE", indicador: "penetracao", vazio: undefined });
    expect(f.mock.calls[0]?.[0]).toBe("/api/mapa?ano=2026&uf=SE&indicador=penetracao");
  });
  it("ficha usa ano e sq no caminho, escapados", async () => {
    const f = espiar({ candidato: {}, votos_municipios: [], gastos: {}, receitas: [], contas_parciais: false });
    await criarCliente().ficha(2026, "a/b");
    expect(f.mock.calls[0]?.[0]).toBe("/api/candidatos/2026/a%2Fb");
  });
  it("erro HTTP falha alto com status e caminho", async () => {
    simular({}, false);
    await expect(criarCliente().gastos({})).rejects.toThrow(/\/gastos.*500/);
  });
  it("resposta que não é objeto é rejeitada, não repassada", async () => {
    simular([1, 2]);
    await expect(criarCliente().grupos()).rejects.toThrow(/inesperada/);
  });
  it("resposta sem as chaves obrigatórias é rejeitada", async () => {
    simular({ foo: 1 });
    await expect(criarCliente().candidatos({})).rejects.toThrow(/inesperada.*candidatos/);
  });
  it("expõe todos os endpoints do contrato", () => {
    const c = criarCliente();
    for (const m of ["meta", "grupos", "candidatos", "ficha", "mapa", "pontos", "gastos", "comparativo", "municipio"] as const) expect(typeof c[m]).toBe("function");
  });
});
