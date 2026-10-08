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

describe("deep-link dos lados da Evolução (#/evolucao?de=c:1,2&para=g:missao_2026)", () => {
  it("lê e grava cada lado; vírgula pode vir codificada", () => {
    expect(lerHash("#/evolucao?de=c:1,2&para=g:missao_2026")?.filtros).toMatchObject({ de: "c:1,2", para: "g:missao_2026" });
    expect(lerHash("#/evolucao?de=c%3A1%2C2")?.filtros.de).toBe("c:1,2");
    expect(decodeURIComponent(formatarHash("evolucao", { ...FILTROS_PADRAO, de: "c:1,2", para: "g:missao_2026" }))).toBe("#/evolucao?de=c:1,2&para=g:missao_2026");
  });
  it("sem escolha, não polui a URL; lixo é descartado", () => {
    expect(lerHash("#/evolucao")?.filtros).toMatchObject({ de: "", para: "" });
    expect(formatarHash("evolucao", FILTROS_PADRAO)).toBe("#/evolucao");
    expect(lerHash("#/evolucao?de=c:1,../x,<b>,2&para=g:<x>")?.filtros).toMatchObject({ de: "c:1,2", para: "" });
  });
});
