import { describe, expect, it } from "vitest";
import {
  BLOCOS, blocoInicial, buscarNossos, celula, escolherNosso, linhasDaTabela, paramsReferencias, pontosDeIndice, ufInicial, FORMATO_INDICE, hashDaFicha, INDICADORES,
  type CandidatoRef,
} from "../../src/dados/referencias-logica";

const perfil = (o: Partial<Record<string, number | null>> = {}) => ({
  votos: null, pct_validos: null, penetracao: null, n_municipios: null, hhi: null, n_efetivo_municipios: null,
  custo_voto_pago: null, receita_total: null, pct_publico: null, pct_pessoa_fisica: null, ...o,
});
const cand = (sq: number, nome: string, votos: number, extra: Partial<CandidatoRef> = {}): CandidatoRef => ({
  sq_candidato: sq, nm_urna: nome, votos, destacado: false, indicadores: perfil({ votos }), motivos: {}, indices: null, ...extra,
} as CandidatoRef);

describe("blocos e parâmetros", () => {
  it("são três, na ordem Presidente, Dep. federal, Dep. estadual", () => {
    expect(BLOCOS.map((b) => b.id)).toEqual(["presidente", "deputado_federal", "deputado_estadual"]);
  });
  it("presidente não manda UF; deputado manda UF e, se houver, o sq escolhido", () => {
    expect(paramsReferencias("presidente", "SP", "9")).toEqual({ cargo: "PRESIDENTE" });
    expect(paramsReferencias("deputado_federal", "SP", null)).toEqual({ cargo: "DEPUTADO FEDERAL", uf: "SP" });
    expect(paramsReferencias("deputado_estadual", "SE", "12")).toEqual({ cargo: "DEPUTADO ESTADUAL", uf: "SE", sq: "12" });
  });
  it("bloco inicial segue o cargo do filtro global; cargos sem referência caem em Dep. federal", () => {
    expect(blocoInicial("presidente")).toBe("presidente");
    expect(blocoInicial("deputado_estadual")).toBe("deputado_estadual");
    expect(blocoInicial("senador")).toBe("deputado_federal");
  });
  it("UF inicial segue o filtro; Brasil (BR) vira SP", () => {
    expect(ufInicial("SE")).toBe("SE");
    expect(ufInicial("BR")).toBe("SP");
  });
});

describe("escolha do nosso candidato", () => {
  const a = cand(1, "ANA", 500), b = cand(2, "BRUNO", 900), c = cand(3, "CARLA", 100, { destacado: true });
  it("padrão: o destacado pela API; sem destaque, o mais votado", () => {
    expect(escolherNosso([a, b, c])?.sq_candidato).toBe(3);
    expect(escolherNosso([a, b])?.sq_candidato).toBe(2);
    expect(escolherNosso([])).toBeNull();
  });
  it("busca por nome ignora acento e caixa, pede 2 letras e devolve poucos", () => {
    const l = [cand(1, "JOSÉ DA SILVA", 1), cand(2, "Josefa", 2), cand(3, "MARIA", 3)];
    expect(buscarNossos(l, "jose").map((x) => x.sq_candidato)).toEqual([1, 2]);
    expect(buscarNossos(l, "j")).toEqual([]);
    expect(buscarNossos(Array.from({ length: 30 }, (_, i) => cand(i, `NOME ${String(i)}`, i)), "nome")).toHaveLength(8);
  });
});

describe("célula: dado ausente nunca vira zero", () => {
  it("nulo → 'sem dado' com o motivo da API", () => {
    const c = cand(1, "X", 10, { motivos: { custo_voto_pago: "sem prestação de contas" } });
    expect(celula(c, "custo_voto_pago")).toEqual({ texto: "sem dado", semDado: true, motivo: "sem prestação de contas" });
    expect(celula(c, "hhi")).toEqual({ texto: "sem dado", semDado: true, motivo: "" });
  });
  it("zero verdadeiro continua zero", () => {
    const c = cand(1, "X", 0, { indicadores: perfil({ pct_publico: 0 }) });
    expect(celula(c, "pct_publico").texto).toBe("0,0 %");
    expect(celula(c, "pct_publico").semDado).toBe(false);
  });
  it("formata por tipo (votos, %, ‰, R$/voto)", () => {
    const c = cand(1, "X", 12345, { indicadores: perfil({ votos: 12345, pct_validos: 1.234, penetracao: 4.56, custo_voto_pago: 7.5 }) });
    expect(celula(c, "votos").texto).toBe("12.345");
    expect(celula(c, "pct_validos").texto).toBe("1,2 %");
    expect(celula(c, "penetracao").texto).toBe("4,6 ‰");
    expect(celula(c, "custo_voto_pago").texto).toMatch(/^R\$\s?7,50$/);
  });
});

describe("tabela lado a lado", () => {
  const ref = [cand(10, "R1", 1000), cand(11, "R2", 800)];
  const nosso = cand(1, "ANA", 50, { indices: perfil({ votos: 0.05, pct_validos: 0.1 }) });
  it("uma linha por indicador, colunas = referência + mediana + nosso", () => {
    const med = perfil({ votos: 900 });
    const linhas = linhasDaTabela(ref, med, nosso);
    expect(linhas[0]?.chave).toBe("votos");
    expect(linhas[0]?.referencia.map((x) => x.texto)).toEqual(["1.000", "800"]);
    expect(linhas[0]?.mediana.texto).toBe("900");
    expect(linhas[0]?.nosso?.texto).toBe("50");
    const hhi = linhas.find((l) => l.chave === "hhi");
    expect(hhi?.mediana.semDado).toBe(true);
  });
  it("sem nosso candidato a coluna fica nula", () => {
    expect(linhasDaTabela(ref, perfil(), null)[0]?.nosso).toBeNull();
  });
});

describe("índice relativo à mediana", () => {
  it("só entra o que tem índice; contexto (votos, receita) fica de fora; ordem fixa", () => {
    const n = cand(1, "ANA", 50, { indices: perfil({ votos: 0.05, pct_validos: 0.1, penetracao: 0.1, custo_voto_pago: 2.5, pct_publico: null, receita_total: 0.3 }) });
    const p = pontosDeIndice(n);
    expect(p.map((x) => x.chave)).toEqual(["pct_validos", "penetracao", "custo_voto_pago"]);
    expect(p[2]?.valor).toBe(2.5);
    expect(p[0]?.rotulo).toBe("% dos válidos");
  });
  it("sem índices (mediana ausente) → lista vazia", () => {
    expect(pontosDeIndice(cand(1, "A", 1))).toEqual([]);
    expect(pontosDeIndice(null)).toEqual([]);
  });
  it("formata em × com vírgula", () => {
    expect(FORMATO_INDICE(0.4)).toBe("0,4×");
    expect(FORMATO_INDICE(1)).toBe("1,0×");
  });
});

describe("link para a ficha", () => {
  it("leva ao candidato do ano, com UF e cargo do próprio candidato", () => {
    const c = cand(77, "ANA", 1, { sg_uf: "SP", cargo: "DEPUTADO ESTADUAL", ano: 2026 });
    const h = hashDaFicha(c);
    expect(h.startsWith("#/candidato")).toBe(true);
    expect(h).toContain("cand=2026%3A77");
    expect(h).toContain("uf=SP");
    expect(h).toContain("cargo=deputado_estadual");
  });
});

describe("campos da T-B21 (receita por voto, despesa ÷ receita)", () => {
  const com = (rv: number | null, ds: number | null, alerta?: boolean): CandidatoRef =>
    cand(5, "X", 10, { indicadores: { ...perfil({ votos: 10 }), receita_por_voto: rv, despesa_sobre_receita: ds }, ...(alerta === undefined ? {} : { alerta_declaracao: alerta }) });
  it("API sem os campos: as duas linhas nem aparecem", () => {
    const chaves = linhasDaTabela([cand(1, "R", 1)], perfil(), cand(2, "N", 1)).map((l) => l.chave);
    expect(chaves).not.toContain("receita_por_voto");
    expect(chaves).not.toContain("despesa_sobre_receita");
  });
  it("API com os campos: linhas aparecem; nulo é 'sem dado', não zero", () => {
    const linhas = linhasDaTabela([com(2.5, 0.9), com(null, null)], { ...perfil(), receita_por_voto: 2.5 }, com(3, 1.2, true));
    const rv = linhas.find((l) => l.chave === "receita_por_voto");
    expect(rv?.referencia.map((x) => x.texto)).toEqual(["R$ 2,50", "sem dado"]);
    expect(linhas.find((l) => l.chave === "despesa_sobre_receita")?.nosso?.texto).toBe("1,20");
  });
  it("R$/voto nas duas bases: despesa paga e receita", () => {
    const rot = INDICADORES.filter((d) => d.chave === "custo_voto_pago" || d.chave === "receita_por_voto").map((d) => d.rotulo);
    expect(rot).toEqual(["Receita por voto", "Custo por voto (despesa paga)"].sort((a, b) => rot.indexOf(a) - rot.indexOf(b)));
    expect(rot).toHaveLength(2);
  });
});
