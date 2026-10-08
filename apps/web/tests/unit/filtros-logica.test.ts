import { describe, expect, it } from "vitest";
import { criarStore, CARGOS, FILTROS_PADRAO } from "../../src/store";
import { lerHash } from "../../src/rotas";
import { contagemTexto, normalizarFiltros, opcoesDeUf, resumoDeGrupo, ROTULO_CARGO } from "../../src/filtros-logica";

describe("filtros dependentes", () => {
  it("não existe mais 'todos os cargos': o padrão é deputado federal", () => {
    expect(CARGOS).not.toContain("todos");
    expect(FILTROS_PADRAO.cargo).toBe("deputado_federal");
  });
  it("hash antigo com cargo=todos cai no padrão sem quebrar", () => {
    expect(lerHash("#/mapa?cargo=todos")?.filtros.cargo).toBe("deputado_federal");
  });
  it("presidente força Brasil; outros cargos mantêm a UF", () => {
    expect(normalizarFiltros({ ...FILTROS_PADRAO, cargo: "presidente", uf: "SP" }).uf).toBe("BR");
    expect(normalizarFiltros({ ...FILTROS_PADRAO, cargo: "senador", uf: "SP" }).uf).toBe("SP");
  });
  it("o store aplica a normalização (presidente + UF não coexistem)", () => {
    const s = criarStore();
    s.definir({ uf: "SP" });
    s.definir({ cargo: "presidente" });
    expect(s.obter().filtros.uf).toBe("BR");
  });
  it("rótulos legíveis de cargo", () => {
    expect(ROTULO_CARGO["deputado_federal"]).toBe("Deputado federal");
    expect(ROTULO_CARGO["presidente"]).toBe("Presidente");
  });
});

describe("contagem ao vivo", () => {
  it("singular, plural e zero com orientação", () => {
    expect(contagemTexto(1)).toBe("1 candidatura");
    expect(contagemTexto(547)).toBe("547 candidaturas");
    expect(contagemTexto(0)).toMatch(/nenhuma candidatura/i);
  });
});

describe("grupo com descrição curta", () => {
  it("monta a descrição a partir do que a API informa (sem lista fixa)", () => {
    expect(resumoDeGrupo({ rotulo: "MBL 2026 (Missão + aliados em outros partidos)", ano: 2026, n_candidaturas: 4 }))
      .toBe("MBL 2026 (Missão + aliados em outros partidos) — eleição de 2026, 4 candidaturas.");
    expect(resumoDeGrupo({ rotulo: "X", ano: 2022, n_candidaturas: 1 })).toBe("X — eleição de 2022, 1 candidatura.");
    expect(resumoDeGrupo({ rotulo: "X", ano: 2022 })).toBe("X — eleição de 2022.");
    expect(resumoDeGrupo(undefined)).toBe("");
  });
});

describe("busca de UF", () => {
  it("sem consulta lista Brasil e todas as UFs, Brasil primeiro", () => {
    const todas = opcoesDeUf("");
    expect(todas).toHaveLength(28);
    expect(todas[0]).toEqual({ valor: "BR", texto: "Brasil" });
  });
  it("acha por nome sem acento ou por sigla", () => {
    expect(opcoesDeUf("sao p").map((o) => o.valor)).toEqual(["SP"]);
    expect(opcoesDeUf("pa").map((o) => o.valor)).toEqual(expect.arrayContaining(["PA", "PB", "PR"]));
    expect(opcoesDeUf("zzz")).toEqual([]);
  });
  it("com UFs disponíveis, só lista as que têm candidatura (Brasil sempre)", () => {
    const so = opcoesDeUf("", new Set(["SE", "SP"])).map((o) => o.valor);
    expect(so).toEqual(["BR", "SE", "SP"]);
    expect(opcoesDeUf("s", new Set(["SE", "AC"])).map((o) => o.valor)).toEqual(["BR", "SE"]);
  });
  it("sigla exata vem antes das demais", () => {
    expect(opcoesDeUf("pa")[0]?.valor).toBe("PA");
  });
});
