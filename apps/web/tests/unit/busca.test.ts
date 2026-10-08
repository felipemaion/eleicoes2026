import { describe, expect, it } from "vitest";
import { destacarTrecho, hashDaCandidatura, linhaDaSugestao, ordenarSugestoes, paramsDaBusca } from "../../src/componentes/busca/busca-logica";
import type { CandidaturaBusca } from "../../src/dados/contrato";

const renan: CandidaturaBusca = {
  ano: 2026, sq_candidato: 280002540694, nm_urna: "RENAN SANTOS", nome: "RENAN SANTOS", numero: 1414, cargo: "PRESIDENTE", uf: "BR",
  partido: { numero: 14, sigla: "MISSÃO" }, votos: 2675887, resultado: "NÃO ELEITO", indicado: false, pessoa_id_publico: "x", abrangencia: { tipo: "pais", uf: null },
};

describe("destacarTrecho", () => {
  it("marca o trecho sem diferenciar acento nem caixa, preservando o texto original", () => {
    expect(destacarTrecho("Renan Santos", "san")).toEqual([{ texto: "Renan ", marca: false }, { texto: "San", marca: true }, { texto: "tos", marca: false }]);
    expect(destacarTrecho("CAPITÃO CONTAR", "capitao")).toEqual([{ texto: "CAPITÃO", marca: true }, { texto: " CONTAR", marca: false }]);
  });
  it("sem correspondência ou consulta vazia devolve o texto inteiro", () => {
    expect(destacarTrecho("Kim", "zzz")).toEqual([{ texto: "Kim", marca: false }]);
    expect(destacarTrecho("Kim", "  ")).toEqual([{ texto: "Kim", marca: false }]);
  });
});

describe("sugestão", () => {
  it("linha traz ano, cargo, UF, partido e votos", () => {
    expect(linhaDaSugestao(renan)).toBe("2026 · Presidente · Brasil · MISSÃO (14) · 2.675.887 votos");
  });
  it("uf aparece como sigla e votos zerados não somem", () => {
    expect(linhaDaSugestao({ ...renan, cargo: "DEPUTADO ESTADUAL", uf: "RN", votos: 0 })).toBe("2026 · Deputado estadual · RN · MISSÃO (14) · 0 votos");
  });
});

describe("navegação", () => {
  it("ficha leva ao deep-link do candidato com o contexto dele", () => {
    expect(hashDaCandidatura(renan, "candidato")).toBe("#/candidato?cargo=presidente&cand=2026%3A280002540694");
  });
  it("mapa fixa o candidato no mapa", () => {
    expect(hashDaCandidatura({ ...renan, cargo: "SENADOR", uf: "MS", abrangencia: { tipo: "uf", uf: "MS" } }, "mapa")).toBe("#/mapa?uf=MS&cargo=senador&cand=2026%3A280002540694");
  });
  it("candidato de 2022 leva o grupo de 2022 (filtros coerentes na barra)", () => {
    expect(hashDaCandidatura({ ...renan, ano: 2022, cargo: "DEPUTADO FEDERAL", uf: "SP" }, "candidato")).toBe("#/candidato?uf=SP&grupo=mbl_2022&ano=2022&cand=2022%3A280002540694");
  });
});

describe("params da busca", () => {
  it("manda q e os filtros presentes; 'BR' e vazio ficam de fora", () => {
    expect(paramsDaBusca("kim", { uf: "BR", cargo: "deputado_federal", ano: 2026 })).toEqual({ q: "kim", limite: "40" });
    expect(paramsDaBusca(" kim ", { uf: "SP", cargo: "deputado_federal", ano: 2026 }, true)).toEqual({ q: "kim", limite: "40", uf: "SP", cargo: "DEPUTADO FEDERAL", ano: "2026" });
  });
});

describe("ordenarSugestoes", () => {
  const c = (nm: string, votos: number, ano = 2026): CandidaturaBusca => ({ ...renan, nm_urna: nm, nome: nm, votos, ano, sq_candidato: votos });
  it("nome que COMEÇA pela consulta vem antes; depois mais votado; 2026 desempata 2022", () => {
    const ordem = ordenarSugestoes([c("CAPITÃO RENAN", 900), c("DR RENAN", 5), c("RENAN SANTOS", 2_000_000), c("RENAN MELO", 500, 2022), c("RENAN MELO", 500)], "renan").map((x) => `${x.nm_urna}/${String(x.ano)}`);
    expect(ordem).toEqual(["RENAN SANTOS/2026", "RENAN MELO/2026", "RENAN MELO/2022", "CAPITÃO RENAN/2026", "DR RENAN/2026"]);
  });
  it("ignora acento e caixa e não altera o vetor de entrada", () => {
    const e = [c("ZÉ", 1), c("JOSÉ", 99)];
    expect(ordenarSugestoes(e, "ze")[0]?.nm_urna).toBe("ZÉ");
    expect(e[0]?.nm_urna).toBe("ZÉ");
  });
});
