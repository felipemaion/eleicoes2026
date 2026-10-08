import { describe, expect, it } from "vitest";
import { formatarHash, lerHash } from "../../src/rotas";
import { FILTROS_PADRAO } from "../../src/store";

describe("deep-link do candidato (#/candidato?cand=ano:sq)", () => {
  it("lê e grava o candidato escolhido", () => {
    expect(lerHash("#/candidato?cand=2026:1")?.filtros.candidato).toBe("2026:1");
    expect(formatarHash("candidato", { ...FILTROS_PADRAO, candidato: "2026:1" })).toBe("#/candidato?cand=2026%3A1");
  });
  it("padrão é vazio e não aparece na URL", () => {
    expect(lerHash("#/candidato")?.filtros.candidato).toBe("");
    expect(formatarHash("candidato", FILTROS_PADRAO)).toBe("#/candidato");
  });
  it("valor mal formado vira vazio (nada de injeção na URL da API)", () => {
    expect(lerHash("#/candidato?cand=../../x")?.filtros.candidato).toBe("");
    expect(lerHash("#/candidato?cand=2026:1/2")?.filtros.candidato).toBe("");
  });
});

describe("deep-link da seleção da Evolução (#/evolucao?pessoas=a,b)", () => {
  const A = "aaaaaaaaaaaa";
  const B = "bbbbbbbbbbbb";
  it("lê e grava a lista de pessoas", () => {
    expect(lerHash(`#/evolucao?pessoas=${A},${B}`)?.filtros.pessoas).toBe(`${A},${B}`);
    expect(lerHash(`#/evolucao?pessoas=${A}%2C${B}`)?.filtros.pessoas).toBe(`${A},${B}`);
    expect(decodeURIComponent(formatarHash("evolucao", { ...FILTROS_PADRAO, pessoas: `${A},${B}` }))).toBe(`#/evolucao?pessoas=${A},${B}`);
  });
  it("sem seleção, não polui a URL; lixo é descartado", () => {
    expect(lerHash("#/evolucao")?.filtros.pessoas).toBe("");
    expect(formatarHash("evolucao", FILTROS_PADRAO)).toBe("#/evolucao");
    expect(lerHash(`#/evolucao?pessoas=${A},../x,<b>`)?.filtros.pessoas).toBe(A);
  });
});
