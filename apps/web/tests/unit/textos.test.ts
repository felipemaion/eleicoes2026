import { describe, expect, it } from "vitest";
import { avisosDaTela, definicaoDe, formatarDtGeracao, formatarMesBase, indicadorDe, notaRodape, preencher, subtituloDaTela } from "../../src/textos";

describe("placeholders", () => {
  it("dt_geracao: data ISO → dd/mm/aaaa; com hora → dd/mm/aaaa hh:mm", () => {
    expect(formatarDtGeracao("2026-10-07")).toBe("07/10/2026");
    expect(formatarDtGeracao("2026-10-07T08:00:00")).toBe("07/10/2026 08:00");
  });
  it("dt_geracao inválida falha alto (nunca imprime data inventada)", () => {
    expect(() => formatarDtGeracao("ontem")).toThrow(/dt_geracao/);
  });
  it("mês-base AAAA-MM → mmm/aaaa", () => {
    expect(formatarMesBase("2026-09")).toBe("set/2026");
    expect(() => formatarMesBase("2026-13")).toThrow(/mês-base/);
  });
  it("preencher troca {dt_geracao} e {mes_base_ipca}; valor ausente vira 'indisponível', não chave crua", () => {
    expect(preencher("Gerado em {dt_geracao}.", { dt_geracao: "2026-10-07" })).toBe("Gerado em 07/10/2026.");
    expect(preencher("R$ de {mes_base_ipca}", {})).toBe("R$ de indisponível");
    expect(preencher("sem marcador", {})).toBe("sem marcador");
  });
});

describe("textos públicos (docs/metodologia/publico/textos.json)", () => {
  it("indicador traz título, como ler, unidade, denominador e cuidado preenchidos", () => {
    const i = indicadorDe("penetracao", {});
    expect(i.titulo).toMatch(/Penetração/);
    expect(i.como_ler.length).toBeGreaterThan(20);
    expect(i.unidade).toBeTruthy();
  });
  it("indicador inexistente falha alto", () => {
    expect(() => indicadorDe("nao_existe", {})).toThrow(/nao_existe/);
  });
  it("glossário: definição por termo", () => {
    expect(definicaoDe("eleitores_aptos").definicao).toMatch(/denominador/);
  });
  it("subtítulo e rodapé por tela, com a data de geração aplicada", () => {
    expect(subtituloDaTela("visao-geral")).toMatch(/Missão/);
    expect(notaRodape("gastos", { dt_geracao: "2026-10-07", mes_base_ipca: "2026-09" })).toMatch(/07\/10\/2026.*set\/2026/);
  });
  it("avisos: contas parciais só com a flag; IPCA só com mês-base; n_baixo no mapa (que tem hachura)", () => {
    const base = { dt_geracao: "2026-10-07", contas_parciais: false, mes_base_ipca: undefined };
    expect(avisosDaTela("gastos", base).map((a) => a.chave)).toEqual([]);
    expect(avisosDaTela("gastos", { ...base, contas_parciais: true, mes_base_ipca: "2026-09" }).map((a) => a.chave)).toEqual(["contas_parciais", "ipca"]);
    const mapa = avisosDaTela("mapa", base).map((a) => a.chave);
    expect(mapa).toContain("rezoneamento");
    expect(mapa).toContain("n_baixo");
  });
  it("aviso preenche dt_geracao no texto", () => {
    const [a] = avisosDaTela("visao-geral", { dt_geracao: "2026-10-07", contas_parciais: true });
    expect(a?.texto).toContain("07/10/2026");
    expect(a?.nivel).toBe("atencao");
  });
});
