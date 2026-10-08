import { describe, expect, it } from "vitest";
import comparativo from "../fixtures/api/comparativo.json";
import gastos from "../fixtures/api/gastos.json";
import { gastosTipados } from "../fixtures/api/tipado";
import { kpisDeReceita, linhasDoComparativoReceitas, notaFaixaReceita, pontosDeReceita } from "../../src/dados/receitas-logica";
import type { ComparativoReceitas, IndicadorComparado, RespostaGastos } from "../../src/dados/contrato";

const G: RespostaGastos = gastosTipados(gastos);
const R = comparativo.receitas as ComparativoReceitas;

describe("kpisDeReceita", () => {
  it("receita líquida, por voto, % público, % autofinanciamento, % PF e saldo, cada um com fonte", () => {
    const k = kpisDeReceita(G);
    expect(k.map((x) => x.rotulo)).toEqual([
      "Receita total do grupo", "Receita por voto", "% recursos públicos", "% autofinanciamento", "% pessoas físicas", "Saldo da campanha",
    ]);
    expect(k[0]).toMatchObject({ valor: 290000, formato: "moeda", ajuda: "receitas_grupo", fonte: "contas" });
    expect(k[1]).toMatchObject({ valor: 8.74, ajuda: "receita_por_voto" });
    expect(k[5]).toMatchObject({ valor: -53000, ajuda: "saldo_campanha" });
    expect(k.every((x) => x.fonte === "contas")).toBe(true);
  });
  it("indicador nulo some em vez de virar zero; sem receitas devolve só o que existe", () => {
    const k = kpisDeReceita({ ...G, receitas: null, receita_por_voto: { ...G.receita_por_voto, receita_por_voto: null }, saldo: { ...G.saldo, saldo_contratado: null } });
    expect(k).toEqual([]);
  });
});

describe("pontosDeReceita", () => {
  it("um ponto por candidato com receita; custo do eixo é a receita bruta", () => {
    const p = pontosDeReceita(G);
    expect(p).toHaveLength(3);
    expect(p[0]).toMatchObject({ id: "1", rotulo: "Ana Souza", custo: 210000, votos: 18049, foto: "/fotos/2026/1.webp" });
    const d = Object.fromEntries(p[0]?.detalhe ?? []);
    expect(d["Receita total"]).toMatch(/210\.000/);
    expect(d["Receita por voto"]).toMatch(/11,63/);
    expect(d["Saldo (receita − despesa contratada)"]).toMatch(/13\.000/);
    expect(d["% recursos públicos"]).toMatch(/62,5/);
    expect(d["% pessoas físicas"]).toMatch(/10/);
  });
  it("candidato sem linha de receita (null ≠ zero) fica de fora", () => {
    const sem = { ...G, por_candidato: G.por_candidato.map((c, i) => (i === 1 ? { ...c, receita_total: null } : c)) };
    expect(pontosDeReceita(sem).map((x) => x.id)).toEqual(["1", "3"]);
  });
});

describe("notaFaixaReceita", () => {
  it("mostra a faixa quando há repasse de doador desconhecido", () => {
    expect(notaFaixaReceita(G)).toMatch(/280\.000.*290\.000/);
  });
  it("null sem faixa", () => {
    expect(notaFaixaReceita({ ...G, receitas: null })).toBeNull();
    expect(notaFaixaReceita({ ...G, receitas: { ...(G.receitas as NonNullable<typeof G.receitas>), faixa_receita: null } })).toBeNull();
  });
});

describe("linhasDoComparativoReceitas", () => {
  it("monetários em R$ (2022 corrigido) com variação %, percentuais em p.p.", () => {
    const l = linhasDoComparativoReceitas(R);
    const total = l.find((x) => x.chave === "receita_total");
    expect(total).toMatchObject({ rotulo: "Receita total", ajuda: "comparacao_receitas" });
    expect(total?.de).toMatch(/260\.000/);
    expect(total?.deNominal).toMatch(/200\.000/);
    expect(total?.para).toMatch(/290\.000/);
    expect(total?.variacao).toMatch(/\+11,5\s?%/);
    const pub = l.find((x) => x.chave === "pct_publico");
    expect(pub?.rotulo).toBe("% recursos públicos");
    expect(pub?.de).toMatch(/40/);
    expect(pub?.variacao).toMatch(/\+46,2 p\.p\./);
  });
  it("chave desconhecida mantém um rótulo legível em vez de sumir", () => {
    const l = linhasDoComparativoReceitas({ ...R, monetarios: { receita_doacoes_pf: R.monetarios["receita_total"] as IndicadorComparado }, percentuais: {} });
    expect(l[0]?.rotulo).toBe("Receita: doacoes pf");
  });
});
