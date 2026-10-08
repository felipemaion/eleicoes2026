import { describe, expect, it } from "vitest";
import gastos from "../fixtures/api/gastos.json";
import { idsQueCasam, medianaCustoVoto, pontosDeGastos } from "../../src/dados/gastos-logica";
import type { RespostaGastos } from "../../src/dados/contrato";

const G: RespostaGastos = gastos;

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
