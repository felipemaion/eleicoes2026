import { describe, expect, it } from "vitest";
import corr from "../fixtures/api/redes-correlacoes.json";
import redesJson from "../fixtures/api/redes.json";
import serie1 from "../fixtures/api/redes-serie.json";
import serie2 from "../fixtures/api/redes-serie-2pontos.json";
import type { RespostaCorrelacoes, RespostaRedes } from "../../src/dados/contrato";
import {
  buscarCandidatos, descreverStatus, detalheExcluidos, fraseResumo, interpretarCorrelacao, kpisDeRedes, paramsRedes,
  pontosSeguidoresVotos, rankingsDeRedes, recorteDaTela, ritmoPorJanela, situacaoDaSerie, textoVotoEsperado,
} from "../../src/dados/redes-logica";
import { FILTROS_PADRAO } from "../../src/store";

const redes = redesJson as unknown as RespostaRedes;
const correlacoes = corr as unknown as RespostaCorrelacoes;

describe("paramsRedes", () => {
  it("manda grupo e cargo no formato da API, uf só quando não é Brasil, e nunca o ano", () => {
    expect(paramsRedes({ ...FILTROS_PADRAO })).toEqual({ grupo: "missao_2026", cargo: "DEPUTADO FEDERAL" });
    expect(paramsRedes({ ...FILTROS_PADRAO, uf: "SP" })).toEqual({ grupo: "missao_2026", cargo: "DEPUTADO FEDERAL", uf: "SP" });
  });
});

describe("fraseResumo", () => {
  it("diz o que está sendo comparado: rede, quantas candidaturas, grupo, cargo, UF, com e sem perfil público", () => {
    const f = fraseResumo(redes, "Partido Missão 2026", { ...FILTROS_PADRAO, uf: "SP" });
    expect(f).toBe("Instagram de 14 candidaturas do Partido Missão 2026 · Dep. federal · SP — 10 com perfil público, 4 indisponíveis.");
  });
  it("Brasil e singular", () => {
    const um = { ...redes, agregado: { ...redes.agregado, n_candidatos: 1, n_com_dados: 1 } };
    expect(fraseResumo(um, "G", { ...FILTROS_PADRAO })).toBe("Instagram de 1 candidatura do G · Dep. federal · Brasil — 1 com perfil público, 0 indisponíveis.");
  });
});

describe("detalheExcluidos", () => {
  it("lista cada motivo que existe, sem inventar zeros", () => {
    expect(detalheExcluidos(redes.excluidos)).toBe("Sem Instagram declarado: 1 · Declararam, ainda sem coleta: 1 · Conta pessoal ou inexistente: 2");
    expect(detalheExcluidos({ sem_instagram: 0, nao_coletado: 0, indisponivel: 0, sem_votos: 0 })).toBe("");
    expect(detalheExcluidos({ sem_instagram: 0, nao_coletado: 0, indisponivel: 0, sem_votos: 3 })).toBe("Sem votos registrados: 3");
  });
});

describe("kpisDeRedes", () => {
  it("traz seguidores, mediana, ritmo, vídeo e engajamento — todos com ajuda e fonte — e pula o que é nulo", () => {
    const k = kpisDeRedes(redes);
    expect(k.map((x) => x.rotulo)).toEqual(["Contas com números", "Seguidores somados", "Mediana de seguidores", "Posts por semana na campanha (mediana)", "Vídeos e reels (mediana)", "Engajamento por post (mediana)"]);
    expect(k.every((x) => x.ajuda !== undefined && x.fonte === "instagram")).toBe(true);
    expect(k[0]).toMatchObject({ valor: 10, formato: "inteiro", unidade: "de 14 candidaturas" });
    const sem = kpisDeRedes({ ...redes, agregado: { ...redes.agregado, mediana_pct_video: null, seguidores_total: null } });
    expect(sem.map((x) => x.rotulo)).not.toContain("Vídeos e reels (mediana)");
    expect(sem.map((x) => x.rotulo)).not.toContain("Seguidores somados");
  });
});

describe("interpretarCorrelacao", () => {
  const base = (correlacoes.recortes[0] as (typeof correlacoes.recortes)[0]).pares[0];
  const par = (rho: number | null, extra = {}): RespostaCorrelacoes["recortes"][number]["pares"][number] =>
    ({ ...base, n: 10, n_minimo: 10, rho, ic_inf: 0.1, ic_sup: 0.8, ...extra }) as RespostaCorrelacoes["recortes"][number]["pares"][number];
  it("traduz o coeficiente em palavras, com IC, n e a ressalva de causa", () => {
    expect(interpretarCorrelacao(par(0.47)).resumo).toMatch(/^Relação moderada/);
    expect(interpretarCorrelacao(par(0.47)).detalhe).toBe("Coeficiente de Spearman 0,47 (intervalo de 95 %: 0,10 a 0,80), com 10 candidatos. Mostra associação, não prova causa.");
    expect(interpretarCorrelacao(par(0.05)).resumo).toMatch(/^Quase nenhuma relação/);
    expect(interpretarCorrelacao(par(0.2)).resumo).toMatch(/^Relação fraca/);
    expect(interpretarCorrelacao(par(0.6)).resumo).toMatch(/^Relação forte/);
    expect(interpretarCorrelacao(par(0.9)).resumo).toMatch(/^Relação muito forte/);
  });
  it("sinal negativo vira 'inversa'", () => {
    expect(interpretarCorrelacao(par(-0.2)).resumo).toBe("Relação fraca inversa: quem tem mais, tende a ter menos votos.");
    expect(interpretarCorrelacao(par(0.47)).resumo).toBe("Relação moderada: quem tem mais, tende a ter mais votos.");
  });
  it("poucos candidatos: não calcula e diz o mínimo", () => {
    const r = interpretarCorrelacao(par(null, { n: 7 }));
    expect(r.resumo).toBe("Poucos candidatos com dados (7); só calculamos com pelo menos 10.");
    expect(r.detalhe).toBe("");
  });
});

describe("recorteDaTela / pontosSeguidoresVotos", () => {
  it("escolhe o recorte do cargo e transforma os pontos, com classe acima/abaixo/neutro do esperado", () => {
    const r = recorteDaTela(correlacoes, "DEPUTADO FEDERAL");
    expect(r?.n_candidatos).toBe(10);
    expect(recorteDaTela(correlacoes, "SENADOR")).toBeNull();
    const pts = pontosSeguidoresVotos(r as NonNullable<typeof r>);
    expect(pts).toHaveLength(10);
    const fabio = pts.find((p) => p.rotulo === "Fábio Nunes");
    expect(fabio).toMatchObject({ seguidores: 12000, votos: 11800, classe: "acima", id: "6" });
    expect(fabio?.linkPerfil).toBe("https://www.instagram.com/fabionunes_14/");
    expect(pts.find((p) => p.rotulo === "Diego Prado")?.classe).toBe("abaixo");
    expect(pts.find((p) => p.rotulo === "João Pires")?.classe).toBe("neutro");
    expect(fabio?.detalhe.map(([a]) => a)).toEqual(expect.arrayContaining(["Seguidores", "Votos", "Voto observado ÷ esperado"]));
  });
});

describe("textoVotoEsperado", () => {
  it("2 = o dobro; 0,5 = metade; perto de 1 = dentro do esperado", () => {
    expect(textoVotoEsperado(2)).toBe("2,0× o esperado (acima)");
    expect(textoVotoEsperado(0.5)).toBe("0,5× o esperado (abaixo)");
    expect(textoVotoEsperado(1.05)).toBe("1,1× o esperado (dentro do esperado)");
    expect(textoVotoEsperado(null)).toBe("indisponível");
  });
});

describe("rankingsDeRedes", () => {
  it("top 10 por seguidores, engajamento e voto acima do esperado; só quem tem dado", () => {
    const r = rankingsDeRedes(redes);
    expect(r.seguidores[0]).toMatchObject({ rotulo: "Gabi Torres", valor: 76000 });
    expect(r.seguidores.length).toBeLessThanOrEqual(10);
    expect(r.engajamento[0]?.rotulo).toBe("Hugo Alves");
    expect(r.acimaDoEsperado[0]?.rotulo).toBe("Fábio Nunes");
    expect(r.acimaDoEsperado[0]?.valor).toBeCloseTo(2.247, 3);
    expect(r.seguidores.map((b) => b.rotulo)).not.toContain("Marta Vieira");
  });
  it("respeita o limite", () => {
    expect(rankingsDeRedes(redes, 3).seguidores).toHaveLength(3);
  });
});

describe("buscarCandidatos", () => {
  it("acha por trecho do nome, sem acento e sem caixa; consulta curta não lista ninguém", () => {
    expect(buscarCandidatos(redes.candidatos, "fabio").map((c) => c.nm_urna)).toEqual(["Fábio Nunes"]);
    expect(buscarCandidatos(redes.candidatos, "A").map((c) => c.nm_urna)).toEqual([]);
    expect(buscarCandidatos(redes.candidatos, "ar", 3)).toHaveLength(3);
  });
});

describe("descreverStatus", () => {
  it("indisponível nunca é zero: cada situação tem sua frase", () => {
    const por = Object.fromEntries(redes.candidatos.map((c) => [c.nm_urna, descreverStatus(c)]));
    expect(por["Ana Souza"]).toBe("Perfil público com números");
    expect(por["Késia Dantas"]).toBe("Conta pessoal: o Instagram só informa números de contas comerciais ou de criador");
    expect(por["Léo Barros"]).toBe("Não declarou Instagram ao TSE");
    expect(por["Marta Vieira"]).toBe("Declarou o perfil; ainda sem coleta");
    expect(por["Nando Reis"]).toBe("Perfil não encontrado no Instagram");
  });
});

describe("ritmoPorJanela", () => {
  it("mediana do grupo por janela (pré, campanha, pós) e o candidato realçado", () => {
    const r = ritmoPorJanela(redes, 6);
    expect(r.map((x) => x.janela)).toEqual(["pre_campanha", "campanha", "pos_eleicao"]);
    expect(r.map((x) => x.rotulo)).toEqual(["Antes da campanha", "Durante a campanha", "Depois da eleição"]);
    expect(r[1]?.candidato).toBeCloseTo(2.1);
    expect(r[1]?.grupo).toBeCloseTo(0.75, 2);
  });
  it("janela curta (<7 dias) não tem taxa semanal: null, nunca zero", () => {
    const r = ritmoPorJanela(redes, 6);
    expect(r[2]?.grupo).toBeNull();
    expect(r[2]?.candidato).toBeNull();
  });
  it("sem candidato escolhido, só o grupo", () => {
    expect(ritmoPorJanela(redes, null).every((x) => x.candidato === null)).toBe(true);
  });
});

describe("situacaoDaSerie", () => {
  it("1 ponto: número + nota; 2+: linha", () => {
    const um = situacaoDaSerie(serie1);
    expect(um).toMatchObject({ tipo: "um_ponto", seguidores: 52000 });
    expect(um.tipo === "um_ponto" && um.nota).toBe("Primeira coleta em 08/10/2026. A série cresce a cada dia.");
    const dois = situacaoDaSerie(serie2);
    expect(dois.tipo).toBe("linha");
    expect(dois.tipo === "linha" && dois.resumo).toBe("+340 seguidores (+0,65 %) em 1 dia");
  });
});
