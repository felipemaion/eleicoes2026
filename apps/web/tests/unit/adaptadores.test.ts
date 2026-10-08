import { describe, expect, it } from "vitest";
import {
  avisosGastos, barrasMunicipios, dispersaoCustoVoto, escalaDoMapa, escalaIgualNosDoisAnos, kpisDoGrupo,
  mapaDeDiferenca, paramsDeFiltros, paresDaComparacao, rankingDeCandidatos,
} from "../../src/dados/adaptadores";
import type { RespostaCandidatos, RespostaComparativo, RespostaGastos, RespostaMapa } from "../../src/dados/contrato";
import { FILTROS_PADRAO } from "../../src/store";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import mapa from "../fixtures/api/mapa.json";

const C = candidatos as RespostaCandidatos;
const G = gastos as RespostaGastos;
const M = mapa as RespostaMapa;
const kpisC = (C.kpis ?? (() => { throw new Error("fixture sem kpis"); })());
const CMP = comparativo as RespostaComparativo;

describe("paramsDeFiltros", () => {
  it("omite BR e 'todos' (padrões da API) e mantém o resto", () => {
    expect(paramsDeFiltros(FILTROS_PADRAO)).toEqual({ ano: "2026", grupo: "missao_2026" });
    expect(paramsDeFiltros({ ...FILTROS_PADRAO, uf: "SE", cargo: "deputado_federal" })).toMatchObject({ uf: "SE", cargo: "deputado_federal" });
  });
});

describe("kpisDoGrupo", () => {
  it("monta os 7 KPIs da spec §8.1 com unidade", () => {
    const k = kpisDoGrupo(kpisC);
    expect(k.map((x) => x.rotulo)).toEqual([
      "Votação do partido", "Penetração", "% dos válidos", "Eleitos / candidaturas aptas",
      "Custo por voto contratado", "% recursos públicos", "Δ penetração vs MBL 2022",
    ]);
    expect(k.find((x) => x.rotulo === "Penetração")?.unidade).toMatch(/aptos/);
  });
  it("sem comparação, o KPI de Δ some em vez de virar 0", () => {
    const k = kpisDoGrupo({ ...kpisC, delta_penetracao: null, penetracao_comparada: null, custo_voto_contratado: null });
    expect(k.some((x) => x.rotulo.startsWith("Δ"))).toBe(false);
    expect(k.some((x) => x.rotulo === "Custo por voto contratado")).toBe(false);
  });
});

describe("rankingDeCandidatos", () => {
  it("ordena por votos e filtra 'só indicados'", () => {
    expect(rankingDeCandidatos(C.candidatos, false).map((b) => b.rotulo)).toEqual(["Ana Souza", "Bruno Lima", "Carla Dias"]);
    expect(rankingDeCandidatos(C.candidatos, true).map((b) => b.rotulo)).toEqual(["Ana Souza", "Bruno Lima"]);
  });
});

describe("gastos", () => {
  it("dispersão mantém zeros (o gráfico os põe na calha, nunca some candidato) e escolhe contratado ou pago", () => {
    const pts = dispersaoCustoVoto({ ...G, candidatos: [...G.candidatos, { id: "9", rotulo: "Zero", votos: 0, custo_contratado: 5, custo_pago: 0 }] }, "contratado");
    expect(pts.map((p) => p.id)).toEqual(["1", "2", "3", "9"]);
    expect(pts[0]).toMatchObject({ custo: 223000, votos: 18049 });
    expect(dispersaoCustoVoto(G, "pago")[0]?.custo).toBe(180000);
  });
  it("avisos: contas parciais e mês-base do deflator, sempre explícitos", () => {
    const a = avisosGastos(G);
    expect(a.join(" ")).toMatch(/parciais/);
    expect(a.join(" ")).toMatch(/2026-09|setembro de 2026/);
    expect(avisosGastos({ ...G, contas_parciais: false }).join(" ")).not.toMatch(/parciais/);
  });
});

describe("mapa", () => {
  it("quantil → escala com meta de taxa (coroplético permitido)", () => {
    const { escala, meta, valores } = escalaDoMapa(M);
    expect(escala.tipo).toBe("quantil");
    expect(meta).toMatchObject({ tipo: "taxa", unidade: "% dos votos válidos" });
    expect(Object.keys(valores)).toHaveLength(75);
  });
  it("divergente usa a extensão da API; sem ela, o maior |valor|", () => {
    const base: RespostaMapa = { ...M, escala_sugerida: "divergente", tipo: "diferenca", valores: { a: -0.02, b: 0.01 } };
    expect(escalaDoMapa(base).escala.tipo).toBe("divergente");
    expect(() => escalaDoMapa({ ...base, valores: {} })).not.toThrow();
  });
  it("recusa resposta sem unidade/denominador (legenda exige)", () => {
    expect(() => escalaDoMapa({ ...M, denominador: "" })).toThrow(/denominador/);
  });
  it("2022 e 2026 compartilham as MESMAS quebras", () => {
    const { antes, depois } = escalaIgualNosDoisAnos(CMP.penetracao_antes, CMP.penetracao_depois);
    expect(antes.quebras).toEqual(depois.quebras);
    const so26 = escalaDoMapa({ ...M, valores: CMP.penetracao_depois }).escala.quebras;
    expect(antes.quebras).not.toEqual(so26);
  });
  it("mapa de diferença é divergente centrado em 0, simétrico", () => {
    const d = mapaDeDiferenca(CMP);
    expect(d.escala.tipo).toBe("divergente");
    expect(d.meta.tipo).toBe("diferenca");
    expect(d.meta.unidade).toMatch(/penetração/i);
    expect(d.valores["2800100"]).toBe(CMP.municipios.find((m) => m.cd_mun_ibge === "2800100")?.delta_penetracao);
  });
});

describe("evolução e candidato", () => {
  it("pares antes/depois por candidato", () => {
    expect(paresDaComparacao(CMP)).toEqual([
      { rotulo: "Ana Souza", antes: 0.009, depois: 0.0123 },
      { rotulo: "Bruno Lima", antes: 0.0095, depois: 0.0081 },
    ]);
  });
  it("barras da ficha: top municípios por votos", () => {
    const b = barrasMunicipios(ficha, 5);
    expect(b).toHaveLength(5);
    expect(b[0]?.valor).toBeGreaterThanOrEqual(b[4]?.valor ?? Infinity);
  });
});
