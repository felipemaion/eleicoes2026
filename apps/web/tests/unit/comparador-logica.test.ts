import { describe, expect, it } from "vitest";
import {
  alternarCandidato, fraseResumo, MAX_POR_LADO, nomeDoLado, paramsComparativo, parseLado, formatarLado, resolverLados, type Lado,
} from "../../src/dados/comparador-logica";

const COMPARACOES = [
  { id: "mbl2022_missao2026", de: "mbl_2022", para: "missao_2026", rotulo: "MBL 2022 → Missão 2026" },
  { id: "mbl2022_mbl2026", de: "mbl_2022", para: "mbl_2026", rotulo: "MBL 2022 → MBL 2026" },
];
const GRUPOS = [
  { id: "mbl_2022", rotulo: "MBL 2022", ano: 2022 },
  { id: "missao_2026", rotulo: "Partido Missão 2026", ano: 2026 },
];
const g = (id: string): Lado => ({ tipo: "grupo", id });
const c = (...sqs: string[]): Lado => ({ tipo: "candidatos", sqs });

describe("lado na URL", () => {
  it("grupo e candidatos ida e volta", () => {
    expect(formatarLado(g("mbl_2022"))).toBe("g:mbl_2022");
    expect(formatarLado(c("1", "22"))).toBe("c:1,22");
    expect(parseLado("g:mbl_2022")).toEqual(g("mbl_2022"));
    expect(parseLado("c:1,22")).toEqual(c("1", "22"));
  });
  it("vazio ou lixo = padrão (null); sq inválido é descartado; limite por lado", () => {
    expect(parseLado("")).toBeNull();
    expect(parseLado("g:<script>")).toBeNull();
    expect(parseLado("x:1")).toBeNull();
    expect(parseLado("c:")).toBeNull();
    expect(parseLado("c:1,abc,1,2")).toEqual(c("1", "2"));
    const muitos = Array.from({ length: MAX_POR_LADO + 5 }, (_, i) => String(i + 1)).join(",");
    expect((parseLado(`c:${muitos}`) as { sqs: string[] }).sqs).toHaveLength(MAX_POR_LADO);
    expect(formatarLado(null)).toBe("");
  });
  it("alternarCandidato liga/desliga e respeita o limite", () => {
    expect(alternarCandidato(["1"], "2")).toEqual(["1", "2"]);
    expect(alternarCandidato(["1", "2"], "1")).toEqual(["2"]);
    const cheio = Array.from({ length: MAX_POR_LADO }, (_, i) => String(i + 1));
    expect(alternarCandidato(cheio, "99")).toEqual(cheio);
  });
});

describe("lados padrão", () => {
  it("sem escolha: a comparação que termina no grupo do filtro; senão a primeira", () => {
    expect(resolverLados(null, null, COMPARACOES, "mbl_2026")).toEqual({ de: g("mbl_2022"), para: g("mbl_2026") });
    expect(resolverLados(null, null, COMPARACOES, "outro")).toEqual({ de: g("mbl_2022"), para: g("missao_2026") });
  });
  it("lado escolhido é mantido; o outro cai no padrão", () => {
    expect(resolverLados(c("5"), null, COMPARACOES, "missao_2026")).toEqual({ de: c("5"), para: g("missao_2026") });
    expect(resolverLados(null, c("7"), COMPARACOES, "missao_2026")).toEqual({ de: g("mbl_2022"), para: c("7") });
  });
});

describe("parâmetros do /comparativo", () => {
  it("dois grupos de uma comparação configurada → `comparacao`", () => {
    expect(paramsComparativo(g("mbl_2022"), g("missao_2026"), "DEPUTADO FEDERAL", "SP", COMPARACOES))
      .toEqual({ cargo: "DEPUTADO FEDERAL", uf: "SP", comparacao: "mbl2022_missao2026" });
  });
  it("dois grupos fora das comparações → um parâmetro por lado", () => {
    expect(paramsComparativo(g("outro_2022"), g("missao_2026"), "DEPUTADO FEDERAL", "BR", COMPARACOES))
      .toEqual({ cargo: "DEPUTADO FEDERAL", grupo_2022: "outro_2022", grupo_2026: "missao_2026" });
  });
  it("dois lados de candidatos → sq_2022 / sq_2026 repetidos", () => {
    expect(paramsComparativo(c("1", "2"), c("9"), "DEPUTADO ESTADUAL", "SP", COMPARACOES))
      .toEqual({ cargo: "DEPUTADO ESTADUAL", uf: "SP", sq_2022: ["1", "2"], sq_2026: ["9"] });
  });
  it("misto: candidatos num lado, grupo no outro, nos dois sentidos", () => {
    expect(paramsComparativo(c("1", "2"), g("missao_2026"), "DEPUTADO FEDERAL", "SP", COMPARACOES))
      .toEqual({ cargo: "DEPUTADO FEDERAL", uf: "SP", sq_2022: ["1", "2"], grupo_2026: "missao_2026" });
    expect(paramsComparativo(g("mbl_2022"), c("9"), "DEPUTADO FEDERAL", "BR", COMPARACOES))
      .toEqual({ cargo: "DEPUTADO FEDERAL", grupo_2022: "mbl_2022", sq_2026: ["9"] });
  });
});

describe("frase-resumo", () => {
  const nomes = new Map([["1", "Kim Kataguiri"], ["2", "Cristiano Beraldo"], ["9", "Rafa Minato"]]);
  it("nome do lado: grupo pelo rótulo, candidatos por '+', e 'e mais N' acima de três", () => {
    expect(nomeDoLado(g("missao_2026"), GRUPOS, nomes)).toBe("Partido Missão 2026");
    expect(nomeDoLado(c("1", "2"), GRUPOS, nomes)).toBe("Kim Kataguiri + Cristiano Beraldo");
    expect(nomeDoLado(c("1", "2", "9", "7", "8"), GRUPOS, new Map([...nomes, ["7", "Fulano"], ["8", "Ciclano"]]))).toBe("Kim Kataguiri, Cristiano Beraldo, Rafa Minato e mais 2");
    expect(nomeDoLado(c("1", "404"), GRUPOS, nomes)).toBe("Kim Kataguiri + candidato 404");
  });
  it("monta a frase com contexto e contagem de candidaturas", () => {
    expect(fraseResumo({ de: "Kim Kataguiri + Cristiano Beraldo", para: "Partido Missão", cargo: "Deputado federal", uf: "São Paulo", nDe: 2, nPara: 49 }))
      .toEqual({ de: "Kim Kataguiri + Cristiano Beraldo", para: "Partido Missão", contexto: "Deputado federal · São Paulo", contagem: "2 candidaturas → 49 candidaturas" });
    expect(fraseResumo({ de: "A", para: "B", cargo: "Deputado federal", uf: "Brasil", nDe: 1, nPara: null }).contagem).toBe("1 candidatura");
    expect(fraseResumo({ de: "A", para: "B", cargo: "X", uf: "Y", nDe: null, nPara: null }).contagem).toBeNull();
  });
});
