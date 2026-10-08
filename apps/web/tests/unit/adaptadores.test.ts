import { describe, expect, it } from "vitest";
import {
  barrasMunicipios, cargoDaApi, filtrosDoCandidato, dispersaoCustoVoto, escalaDoMapa, escalaIgualNosDoisAnos, kpisDoGrupo,
  mapaDeDiferenca, paramsComCargo, paramsDeFiltros, penetracaoDosAnos, rankingDeCandidatos, receitaEmpilhada, soNumeros,
} from "../../src/dados/adaptadores";
import type { Ficha, RespostaCandidatos, RespostaComparativo, RespostaGastos, RespostaMapa } from "../../src/dados/contrato";
import { FILTROS_PADRAO } from "../../src/store";
import { fichaTipada, gastosTipados, listaTipada } from "../fixtures/api/tipado";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import mapa from "../fixtures/api/mapa.json";

const C: RespostaCandidatos = listaTipada(candidatos);
const G: RespostaGastos = gastosTipados(gastos);
const M: RespostaMapa = mapa;
const CMP: RespostaComparativo = comparativo;
const F: Ficha = fichaTipada(ficha);
const primeiro = C.itens[0] ?? (() => { throw new Error("fixture sem candidatos"); })();
const primeiroGasto = G.por_candidato[0] ?? (() => { throw new Error("fixture sem gastos"); })();

describe("parâmetros da API", () => {
  it("omite BR (padrão da API) e traduz o cargo para o enum do OpenAPI", () => {
    expect(paramsDeFiltros(FILTROS_PADRAO)).toEqual({ ano: "2026", grupo: "missao_2026", cargo: "DEPUTADO FEDERAL" });
    expect(paramsDeFiltros({ ...FILTROS_PADRAO, uf: "SE", cargo: "deputado_federal" })).toMatchObject({ uf: "SE", cargo: "DEPUTADO FEDERAL" });
    expect(cargoDaApi("presidente")).toBe("PRESIDENTE");
  });
  it("mapa e comparativo exigem cargo, sempre presente nos filtros", () => {
    expect(paramsComCargo(FILTROS_PADRAO)["cargo"]).toBe("DEPUTADO FEDERAL");
    expect(paramsComCargo({ ...FILTROS_PADRAO, cargo: "senador" })["cargo"]).toBe("SENADOR");
  });
});

describe("kpisDoGrupo", () => {
  it("soma votos, conta candidaturas, eleitos e traz custo/% público do /gastos", () => {
    const k = kpisDoGrupo(C, G);
    expect(k.map((x) => x.rotulo)).toEqual(["Votação nominal do grupo", "Candidaturas", "Eleitos", "Custo por voto contratado", "% recursos públicos"]);
    expect(k[0]).toMatchObject({ valor: 33195, formato: "inteiro" });
    expect(k[2]?.valor).toBe(0); // "NÃO ELEITO" e "SUPLENTE" não contam
    expect(k[4]).toMatchObject({ formato: "pontos", valor: 86.2 });
  });
  it("'NÃO ELEITO' não conta como eleito; 'ELEITO POR QP' conta", () => {
    const l: RespostaCandidatos = { ...C, itens: [{ ...primeiro, resultado: "ELEITO POR QP" }, ...C.itens.slice(1)] };
    expect(kpisDoGrupo(l, G)[2]?.valor).toBe(1);
  });
  it("sem resultado nenhum (apuração não saiu) o KPI de eleitos some; nada vira 0", () => {
    const l: RespostaCandidatos = { ...C, itens: C.itens.map((c) => ({ ...c, resultado: null })) };
    expect(kpisDoGrupo(l, G).map((x) => x.rotulo)).not.toContain("Eleitos");
  });
  it("lista truncada (total > itens) é rotulada como soma parcial", () => {
    const k = kpisDoGrupo({ ...C, total: 900, kpis: null }, G);
    expect(k[0]?.unidade).toMatch(/3 de 900/);
  });
  it("com `kpis` do grupo na resposta, a votação é a exata do recorte (não a soma dos itens) e não é parcial", () => {
    const k = kpisDoGrupo({ ...C, total: 900, kpis: { votos: 1_150_983, aptos: 1, validos: 1, pct_validos: 1, penetracao: 1 } }, G);
    expect(k[0]).toMatchObject({ valor: 1_150_983 });
    expect(k[0]?.unidade).not.toMatch(/parcial|de 900/);
  });
  it("KPI nulo some (custo por voto, % público)", () => {
    const k = kpisDoGrupo(C, { ...G, agregado: { ...G.agregado, custo_voto_contratado: null }, receitas: { ...(G.receitas as NonNullable<typeof G.receitas>), pct_publico: null } });
    expect(k.map((x) => x.rotulo)).toEqual(["Votação nominal do grupo", "Candidaturas", "Eleitos"]);
  });
});

describe("rankingDeCandidatos", () => {
  it("ordena por votos e usa o nome de urna", () => {
    expect(rankingDeCandidatos([...C.itens].reverse()).map((b) => b.rotulo)).toEqual(["Ana Souza", "Bruno Lima", "Carla Dias"]);
  });
});

describe("rankingDeCandidatos — detalhe do tooltip", () => {
  it("leva partido e UF para o tooltip", () => {
    const b = rankingDeCandidatos(C.itens)[0];
    const chaves = (b?.detalhe ?? []).map(([k]) => k);
    expect(chaves).toEqual(expect.arrayContaining(["Partido", "UF"]));
  });
});

describe("gastos", () => {
  it("dispersão mantém zeros e escolhe contratado ou pago", () => {
    const zero = { ...primeiroGasto, sq_candidato: 9, nm_urna: "Zero", custo: { ...primeiroGasto.custo, votos: 0, despesa_contratada: 5 } };
    const pts = dispersaoCustoVoto({ ...G, por_candidato: [...G.por_candidato, zero] }, "contratado");
    expect(pts.map((p) => p.id)).toEqual(["1", "2", "3", "9"]);
    expect(pts[0]).toMatchObject({ custo: 223000, votos: 18049 });
    expect(dispersaoCustoVoto(G, "pago")[0]?.custo).toBe(180000);
  });
  it("receita empilhada: uma barra do grupo com as categorias da API", () => {
    expect(receitaEmpilhada(G)).toEqual([{ rotulo: "Total do grupo", valores: G.receitas?.por_categoria }]);
  });
});

describe("mapa", () => {
  it("quebras sugeridas pela API viram escala de limiares (a legenda é a da API)", () => {
    const { escala, meta, valores, aviso } = escalaDoMapa(M);
    expect(escala.tipo).toBe("limiar");
    expect(escala.quebras).toEqual(M.escala_sugerida.quebras);
    expect(meta).toMatchObject({ tipo: "taxa", unidade: "‰", nome: "Penetração (votos por mil eleitores)" });
    expect(meta.denominador).toMatch(/eleitores aptos/);
    expect(aviso).toBeNull();
    expect(Object.keys(valores)).toHaveLength(74); // 1 território sem dado fica de fora
  });
  it("território sem denominador (null) é 'sem dado', nunca 0", () => {
    expect(soNumeros({ a: 1, b: null })).toEqual({ a: 1 });
    const { detalhes } = escalaDoMapa(M);
    const semDado = Object.entries(M.valores).find(([, v]) => v === null)?.[0] ?? "";
    expect(detalhes[semDado]?.taxa).toBeUndefined();
  });
  it("sem quebras (poucos valores) cai em quantil e repassa o aviso do backend", () => {
    const r: RespostaMapa = { ...M, valores: { a: 1, b: 2 }, detalhes: {}, escala_sugerida: { tipo: "sequencial", paleta: "viridis", quebras: null, aviso: "menos de 2 valores" } };
    const e = escalaDoMapa(r);
    expect(e.escala.tipo).toBe("quantil");
    expect(e.aviso).toBe("menos de 2 valores");
  });
  it("indicador absoluto não vira coroplético: falha alto", () => {
    expect(() => escalaDoMapa({ ...M, indicador: "votos", escala_sugerida: { tipo: "simbolo_proporcional", paleta: "um_matiz", quebras: [] } })).toThrow(/absoluto/);
  });
  it("2022 e 2026 compartilham as MESMAS quebras", () => {
    const pen = penetracaoDosAnos(CMP);
    const { antes, depois } = escalaIgualNosDoisAnos(pen.antes, pen.depois);
    expect(antes.quebras).toEqual(depois.quebras);
  });
  it("mapa de diferença é divergente centrado em 0, em ‰, chaveado por AMC", () => {
    const d = mapaDeDiferenca(CMP);
    expect(d.escala.tipo).toBe("divergente");
    expect(d.meta).toMatchObject({ tipo: "diferenca", unidade: "‰" });
    expect(d.valores["2800100"]).toBe(CMP.municipios.find((m) => m.cd_amc === 2800100)?.delta_penetracao);
  });
});

describe("candidato", () => {
  it("barras da ficha: top municípios por votos", () => {
    const b = barrasMunicipios(F, 5);
    expect(b).toHaveLength(5);
    expect(b[0]?.valor).toBeGreaterThanOrEqual(b[4]?.valor ?? Infinity);
  });
});

describe("filtrosDoCandidato", () => {
  const base = { ano: 2026, cargo: "GOVERNADOR", sg_uf: "RJ" } as const;
  it("deriva cargo, UF, ano e grupo da candidatura", () => {
    expect(filtrosDoCandidato(base)).toEqual({ cargo: "governador", uf: "RJ", ano: 2026, grupo: "missao_2026" });
    expect(filtrosDoCandidato({ ano: 2022, cargo: "DEPUTADO FEDERAL", sg_uf: "SP" })).toEqual({ cargo: "deputado_federal", uf: "SP", ano: 2022, grupo: "mbl_2022" });
  });
  it("presidente (UF BR) vira Brasil; cargo fora da lista de filtros não altera o cargo", () => {
    expect(filtrosDoCandidato({ ano: 2026, cargo: "PRESIDENTE", sg_uf: "BR" })).toMatchObject({ cargo: "presidente", uf: "BR" });
    expect(filtrosDoCandidato({ ano: 2026, cargo: "DEPUTADO DISTRITAL", sg_uf: "DF" })).not.toHaveProperty("cargo");
  });
});

describe("receitas ausentes (contas não publicadas)", () => {
  it("receitaEmpilhada devolve vazio quando `receitas` é null; KPI de % público some", () => {
    const sem = { ...G, receitas: null };
    expect(receitaEmpilhada(sem)).toEqual([]);
    expect(kpisDoGrupo(C, sem).map((x) => x.rotulo)).not.toContain("% recursos públicos");
  });
});
