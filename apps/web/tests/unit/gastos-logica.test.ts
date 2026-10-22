import { describe, expect, it } from "vitest";
import gastos from "../fixtures/api/gastos.json";
import { gastosTipados } from "../fixtures/api/tipado";
import { idsQueCasam, medianaCustoVoto, pontosDeGastos, pontosDespesaReceitaPorVoto } from "../../src/dados/gastos-logica";
import type { RespostaGastos } from "../../src/dados/contrato";

const G: RespostaGastos = gastosTipados(gastos);

describe("pontosDeGastos", () => {
  it("monta as linhas do tooltip só com /gastos (partido, resultado, % público)", () => {
    const [ana] = pontosDeGastos(G, "contratado");
    expect(ana).toMatchObject({ id: "1", rotulo: "Ana Souza", custo: 223000, votos: 18049 });
    const d = Object.fromEntries(ana?.detalhe ?? []);
    expect(d["Partido"]).toContain("MISSÃO");
    expect(d["UF"]).toBe("SE");
    expect(d["Cargo"]).toBe("deputado federal");
    expect(d["Despesa contratada"]).toMatch(/223\.000/);
    expect(d["Despesa paga"]).toMatch(/180\.000/);
    expect(d["Custo por voto (contratado)"]).toMatch(/12,36/);
    expect(d["Votos"]).toBe("18.049");
    expect(d["Resultado"]).toBe("eleito");
    expect(d["% recursos públicos"]).toMatch(/62,5/);
  });
  it("base 'pago' troca o custo do eixo e o custo por voto exibido", () => {
    const [ana] = pontosDeGastos(G, "pago");
    expect(ana?.custo).toBe(180000);
  });
  it("sem % público (null) o tooltip diz 'sem receita' em vez de omitir", () => {
    const [, bruno] = pontosDeGastos(G, "contratado");
    expect(Object.fromEntries(bruno?.detalhe ?? [])["% recursos públicos"]).toBe("indisponível");
    expect(Object.fromEntries(bruno?.detalhe ?? [])["Resultado"]).toBe("não eleito");
  });
  it("custo por voto vira 'sem votos' quando não há voto", () => {
    const um = G.por_candidato[0] ?? (() => { throw new Error("fixture sem gastos"); })();
    const g: RespostaGastos = { ...G, por_candidato: [{ ...um, custo: { ...um.custo, votos: 0, custo_voto_contratado: null } }] };
    expect(Object.fromEntries(pontosDeGastos(g, "contratado")[0]?.detalhe ?? [])["Custo por voto (contratado)"]).toBe("sem votos");
  });
});

describe("medianaCustoVoto", () => {
  it("mediana de custo÷votos só de quem tem os dois positivos", () => {
    const m = medianaCustoVoto([
      { id: "a", rotulo: "a", custo: 100, votos: 10 }, { id: "b", rotulo: "b", custo: 300, votos: 10 },
      { id: "c", rotulo: "c", custo: 50, votos: 10 }, { id: "z", rotulo: "z", custo: 0, votos: 5 }, { id: "y", rotulo: "y", custo: 5, votos: 0 },
    ]);
    expect(m).toBe(10);
  });
  it("sem pontos válidos → null", () => { expect(medianaCustoVoto([])).toBeNull(); });
});

describe("idsQueCasam", () => {
  const p = [{ id: "1", rotulo: "Ana Souza", custo: 1, votos: 1 }, { id: "2", rotulo: "JOÃO da Silva", custo: 1, votos: 1 }];
  it("ignora acento e caixa", () => { expect([...idsQueCasam(p, "joao")]).toEqual(["2"]); });
  it("consulta vazia ou curta não destaca nada", () => { expect(idsQueCasam(p, " ").size).toBe(0); });
});

describe("pontosDespesaReceitaPorVoto (T-W28)", () => {
  const base0 = G.por_candidato[0] as RespostaGastos["por_candidato"][number];
  const cand = (id: number, rec: number | null, rpv: number | null, cc: number | null, cp: number | null, votos = 100) => ({
    ...base0, sq_candidato: id, nm_urna: `C${String(id)}`, receita_total: rec, receita_por_voto: rpv,
    custo: { ...base0.custo, votos, despesa_contratada: 500, despesa_paga: 300, custo_voto_contratado: cc, custo_voto_pago: cp },
  });
  const g = { ...G, por_candidato: [cand(1, 1000, 10, 5, 3), cand(2, 2000, 20, null, 4), cand(3, 0, 0, 6, 6), cand(4, null, null, 7, 7), cand(5, 900, 9, 0, 0, 0)] };

  it("x = receita por voto, y = despesa por voto da base; carrega votos e id", () => {
    const { pontos } = pontosDespesaReceitaPorVoto(g, "contratado");
    expect(pontos[0]).toMatchObject({ id: "1", rotulo: "C1", custo: 10, y: 5, votos: 100 });
    expect(pontosDespesaReceitaPorVoto(g, "pago").pontos[0]?.y).toBe(3);
  });
  it("descarta e conta quem tem null ou zero em qualquer eixo", () => {
    const c = pontosDespesaReceitaPorVoto(g, "contratado");
    expect(c.pontos.map((p) => p.id)).toEqual(["1"]); // 2: sem despesa/voto; 3: receita 0; 4: sem receita; 5: sem votos
    expect(c.semDados).toBe(4);
    const p = pontosDespesaReceitaPorVoto(g, "pago");
    expect(p.pontos.map((q) => q.id)).toEqual(["1", "2"]); // 2 tem custo_voto_pago
    expect(p.semDados).toBe(3);
  });
  it("tooltip traz os dados pedidos, incluindo despesa ÷ receita", () => {
    const d = Object.fromEntries(pontosDespesaReceitaPorVoto(g, "contratado").pontos[0]?.detalhe ?? []);
    for (const k of ["Partido", "UF", "Cargo", "Votos", "Receita total", "Despesa contratada", "Despesa paga", "Receita por voto", "Despesa por voto (contratado)", "Despesa ÷ receita"]) expect(d).toHaveProperty(k);
    expect(d["Despesa ÷ receita"]).toBe("50%"); // 500 ÷ 1000
  });
  it("traz foto e link do TSE para o tooltip rico", () => {
    const [p] = pontosDespesaReceitaPorVoto(g, "contratado").pontos;
    expect(p?.foto).toBe(G.por_candidato[0]?.foto_url);
    expect(p?.linkTse?.url).toContain("divulgacandcontas");
  });
});
