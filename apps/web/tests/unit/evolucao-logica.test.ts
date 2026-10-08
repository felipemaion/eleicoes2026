import { describe, expect, it } from "vitest";
import pessoas from "../fixtures/api/pessoas.json";
import { pessoasTipadas } from "../fixtures/api/tipado";
import { alternarPessoa, idsDe, linhasComparativas, ordenarLinhas, paramsPessoas, parsePessoas, soIndicados } from "../../src/dados/evolucao-logica";

const P = pessoasTipadas(pessoas).itens;

describe("seleção na URL", () => {
  it("parsePessoas aceita só ids de 12 hex, sem repetir, até 50", () => {
    expect(parsePessoas("aaaaaaaaaaaa,bbbbbbbbbbbb,aaaaaaaaaaaa,zzz,<script>")).toEqual(["aaaaaaaaaaaa", "bbbbbbbbbbbb"]);
    expect(parsePessoas("")).toEqual([]);
    expect(parsePessoas(Array.from({ length: 60 }, (_, i) => i.toString(16).padStart(12, "0")).join(",")).length).toBe(50);
  });
  it("alternarPessoa liga e desliga preservando a ordem", () => {
    expect(alternarPessoa(["a".repeat(12)], "b".repeat(12))).toEqual(["a".repeat(12), "b".repeat(12)]);
    expect(alternarPessoa(["a".repeat(12), "b".repeat(12)], "a".repeat(12))).toEqual(["b".repeat(12)]);
  });
  it("paramsPessoas repete o parâmetro (lista no FastAPI) e leva o cargo da primeira pessoa comparável", () => {
    const q = paramsPessoas(["aaaaaaaaaaaa", "bbbbbbbbbbbb"], "DEPUTADO FEDERAL", "SE");
    expect(q).toEqual({ cargo: "DEPUTADO FEDERAL", uf: "SE", pessoas: ["aaaaaaaaaaaa", "bbbbbbbbbbbb"] });
    expect(paramsPessoas(["aaaaaaaaaaaa"], "DEPUTADO FEDERAL", "BR")).not.toHaveProperty("uf");
  });
});

describe("atalhos", () => {
  it("soIndicados mantém quem foi indicado (em qualquer dos anos)", () => {
    expect(soIndicados(P).map((x) => x.nome)).toEqual(["BRUNO LIMA"]);
  });
  it("idsDe só devolve os comparáveis (mesmo cargo, não Senado)", () => {
    expect(idsDe(P)).toEqual(["aaaaaaaaaaaa", "bbbbbbbbbbbb"]);
  });
});

describe("tabela 2022 × 2026", () => {
  const linhas = linhasComparativas(P.filter((x) => ["aaaaaaaaaaaa", "bbbbbbbbbbbb"].includes(x.pessoa_id_publico)), { aaaaaaaaaaaa: { de: 10, para: 12.3 } });
  it("uma linha por pessoa com votos, Δ e cargo/partido de cada ano", () => {
    const ana = linhas.find((l) => l.nome === "ANA SOUZA");
    expect(ana).toMatchObject({ votos_de: 9000, votos_para: 18049, delta_votos: 9049, penetracao_de: 10, penetracao_para: 12.3 });
    expect(ana?.delta_penetracao).toBeCloseTo(2.3);
    expect(ana?.partido_de).toBe("NOVO");
    expect(ana?.partido_para).toBe("MISSÃO");
    expect(ana?.cargo_de).toBe("DEPUTADO FEDERAL");
  });
  it("penetração desconhecida fica null (não zero)", () => {
    const bruno = linhas.find((l) => l.nome === "BRUNO LIMA");
    expect(bruno?.penetracao_para).toBeNull();
    expect(bruno?.delta_penetracao).toBeNull();
  });
  it("ordena por coluna, null sempre no fim, nos dois sentidos", () => {
    expect(ordenarLinhas(linhas, "delta_votos", "desc").map((l) => l.nome)).toEqual(["ANA SOUZA", "BRUNO LIMA"]);
    expect(ordenarLinhas(linhas, "delta_votos", "asc").map((l) => l.nome)).toEqual(["BRUNO LIMA", "ANA SOUZA"]);
    expect(ordenarLinhas(linhas, "delta_penetracao", "asc").map((l) => l.nome)).toEqual(["ANA SOUZA", "BRUNO LIMA"]);
    expect(ordenarLinhas(linhas, "delta_penetracao", "desc").map((l) => l.nome)).toEqual(["ANA SOUZA", "BRUNO LIMA"]);
    expect(ordenarLinhas(linhas, "nome", "asc").map((l) => l.nome)).toEqual(["ANA SOUZA", "BRUNO LIMA"]);
  });
});
