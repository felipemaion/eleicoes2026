import { beforeEach, describe, expect, it } from "vitest";
import { PALETAS } from "../../src/paletas";
import { formatarMoeda, formatarNumero } from "../../src/formato";
import * as kpi from "../../src/componentes/graficos/kpi";
import * as barras from "../../src/componentes/graficos/barras";
import * as ranking from "../../src/componentes/graficos/ranking";
import * as dispersao from "../../src/componentes/graficos/dispersao";
import * as empilhado from "../../src/componentes/graficos/empilhado";
import * as comparacao from "../../src/componentes/graficos/comparacao";
import * as multiplos from "../../src/componentes/graficos/multiplos";
import { formatarCompacto } from "../../src/formato";

let el: HTMLElement;
beforeEach(() => {
  document.body.innerHTML = '<div id="c"></div>';
  el = document.getElementById("c") as HTMLElement;
});

const todasCores = new Set<string>([...PALETAS.sequencial, ...PALETAS.divergente, ...PALETAS.categorica].map((c) => c.toLowerCase()));
function coresUsadas(raiz: Element): string[] {
  return [...raiz.querySelectorAll("[fill],[stroke]")]
    .flatMap((n) => [n.getAttribute("fill"), n.getAttribute("stroke")])
    .filter((c): c is string => !!c && c.startsWith("#"));
}
function tabela(raiz: Element): HTMLTableElement {
  const d = raiz.querySelector("details");
  expect(d).not.toBeNull();
  return d?.querySelector("table") as HTMLTableElement;
}

describe("formatação pt-BR", () => {
  it("moeda e milhar", () => {
    expect(formatarMoeda(1234.56)).toBe("R$ 1.234,56");
    expect(formatarMoeda(0)).toBe("R$ 0,00");
    expect(formatarNumero(1234567)).toBe("1.234.567");
  });
});

describe("kpi", () => {
  it("renderiza um cartão por indicador com valor formatado", () => {
    const g = kpi.render(el, [
      { rotulo: "Votos", valor: 12345, formato: "inteiro" },
      { rotulo: "Gasto", valor: 1234.5, formato: "moeda" },
      { rotulo: "Penetração", valor: 0.0456, formato: "percentual" },
    ]);
    const cartoes = el.querySelectorAll(".kpi");
    expect(cartoes).toHaveLength(3);
    expect(cartoes[0]?.textContent).toContain("12.345");
    expect(cartoes[1]?.textContent).toContain("R$ 1.234,50");
    expect(cartoes[2]?.textContent).toContain("4,6%");
    g.atualizar([{ rotulo: "Votos", valor: 1, formato: "inteiro" }]);
    expect(el.querySelectorAll(".kpi")).toHaveLength(1);
  });
});

describe("barras", () => {
  const dados = [
    { rotulo: "A", valor: 1000 },
    { rotulo: "B", valor: 2500 },
    { rotulo: "C", valor: 10 },
  ];
  it("uma marca por dado, eixo, rótulos, role=img e foco por teclado", () => {
    barras.render(el, dados, { titulo: "Votos por município", formato: formatarNumero });
    const svg = el.querySelector("svg");
    expect(svg?.getAttribute("role")).toBe("group");
    expect(svg?.getAttribute("aria-label")).toContain("Votos por município");
    const marcas = el.querySelectorAll("rect.marca");
    expect(marcas).toHaveLength(3);
    marcas.forEach((m) => {
      expect(m.getAttribute("tabindex")).toBe("0");
      expect(m.getAttribute("aria-label")).toMatch(/: /);
      expect(m.getAttribute("role")).toBe("img");
    });
    expect(el.querySelector("g.eixo-x")).not.toBeNull();
    expect([...el.querySelectorAll("text.rotulo")].map((t) => t.textContent)).toEqual(["A", "B", "C"]);
    expect(tabela(el).querySelectorAll("tbody tr")).toHaveLength(3);
    expect(tabela(el).textContent).toContain("2.500");
  });
  it("atualizar troca as marcas sem duplicar", () => {
    const g = barras.render(el, dados, { titulo: "t" });
    g.atualizar(dados.slice(0, 1));
    expect(el.querySelectorAll("rect.marca")).toHaveLength(1);
    expect(el.querySelectorAll("svg")).toHaveLength(1);
    expect(el.querySelectorAll("details")).toHaveLength(1);
  });
  it("largura da barra é proporcional ao valor", () => {
    barras.render(el, dados, { titulo: "t" });
    const w = [...el.querySelectorAll("rect.marca")].map((m) => Number(m.getAttribute("width")));
    expect((w[1] ?? 0) / (w[0] ?? 1)).toBeCloseTo(2.5, 5);
  });
  it("usa só cores das paletas", () => {
    barras.render(el, dados, { titulo: "t" });
    coresUsadas(el).forEach((c) => { expect(todasCores.has(c.toLowerCase())).toBe(true); });
  });
  it("sem dados mostra mensagem em vez de gráfico vazio", () => {
    barras.render(el, [], { titulo: "t" });
    expect(el.querySelectorAll("rect.marca")).toHaveLength(0);
    expect(el.textContent).toContain("Sem dados");
  });
});

describe("ranking", () => {
  it("ordena decrescente, limita ao topo e numera", () => {
    ranking.render(
      el,
      [
        { rotulo: "A", valor: 1 },
        { rotulo: "B", valor: 5 },
        { rotulo: "C", valor: 3 },
      ],
      { titulo: "Ranking", topo: 2 },
    );
    expect([...el.querySelectorAll("text.rotulo")].map((t) => t.textContent)).toEqual(["1. B", "2. C"]);
    expect(el.querySelectorAll("rect.marca")).toHaveLength(2);
  });
});

describe("dispersão custo × votos (log)", () => {
  const pontos = [
    { id: "1", rotulo: "Ana", custo: 1000, votos: 500 },
    { id: "2", rotulo: "Beto", custo: 100000, votos: 20000 },
    { id: "3", rotulo: "Caio", custo: 0, votos: 300 },
    { id: "4", rotulo: "Dani", custo: 5000, votos: 0 },
    { id: "5", rotulo: "Eli", custo: 0, votos: 0 },
  ];
  it("renderiza todos os pontos, inclusive zeros, sem NaN, e sinaliza-os", () => {
    dispersao.render(el, pontos, { titulo: "Custo × votos" });
    const marcas = el.querySelectorAll("circle.marca");
    expect(marcas).toHaveLength(5);
    marcas.forEach((m) => {
      expect(Number.isFinite(Number(m.getAttribute("cx")))).toBe(true);
      expect(Number.isFinite(Number(m.getAttribute("cy")))).toBe(true);
    });
    expect(el.querySelectorAll("circle.marca.zero")).toHaveLength(3);
    const caio = el.querySelector('circle.marca[data-id="3"]');
    expect(caio?.getAttribute("aria-label")).toContain("custo zero");
    expect(el.querySelector("g.eixo-x")).not.toBeNull();
    expect(el.querySelector("g.eixo-y")).not.toBeNull();
    expect(tabela(el).querySelectorAll("tbody tr")).toHaveLength(5);
  });
  it("pontos zero ficam fora da faixa log (na calha)", () => {
    dispersao.render(el, pontos, { titulo: "t" });
    const cx = (id: string): number => Number(el.querySelector(`circle[data-id="${id}"]`)?.getAttribute("cx"));
    expect(cx("3")).toBeLessThan(cx("1"));
    // a calha termina onde começa a escala log: ESQ (76) + CALHA (26); zero fica antes dela
    expect(cx("3")).toBeLessThan(76 + 26);
    expect(Number(el.querySelector('circle[data-id="4"]')?.getAttribute("cy"))).toBeGreaterThan(420 - 48 - 26);
  });
  it("lista vazia e só zeros não quebram", () => {
    dispersao.render(el, [], { titulo: "t" });
    expect(el.textContent).toContain("Sem dados");
    dispersao.render(el, [{ id: "z", rotulo: "Z", custo: 0, votos: 0 }], { titulo: "t" });
    expect(el.querySelectorAll("circle.marca")).toHaveLength(1);
  });
  it("foco por teclado nos pontos", () => {
    dispersao.render(el, pontos, { titulo: "t" });
    el.querySelectorAll("circle.marca").forEach((m) => { expect(m.getAttribute("tabindex")).toBe("0"); });
  });
});

describe("dispersão: hover, destaque e referência", () => {
  const pts = [
    { id: "1", rotulo: "Ana", custo: 1000, votos: 500, detalhe: [["Partido", "MISSÃO (14)"], ["Votos", "500"]] as const },
    { id: "2", rotulo: "Beto", custo: 100000, votos: 20000, detalhe: [["Partido", "NOVO (30)"]] as const },
  ];
  const balao = (): HTMLElement | null => document.querySelector(".tooltip-flutuante:not([hidden])");
  it("hover e foco abrem o tooltip rico do ponto; sair e Esc fecham", () => {
    dispersao.render(el, pts, { titulo: "t" });
    const m = el.querySelector('circle[data-id="1"]') as SVGElement;
    m.dispatchEvent(new MouseEvent("mouseenter", { clientX: 100, clientY: 100 }));
    expect(balao()?.textContent).toContain("Ana");
    expect(balao()?.textContent).toContain("MISSÃO (14)");
    m.dispatchEvent(new MouseEvent("mouseleave"));
    expect(balao()).toBeNull();
    m.dispatchEvent(new FocusEvent("focus"));
    expect(balao()?.textContent).toContain("Ana");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(balao()).toBeNull();
  });
  it("o ponto expõe o texto do tooltip também em data-tooltip (teste e leitor de tela)", () => {
    dispersao.render(el, pts, { titulo: "t" });
    expect(el.querySelector('circle[data-id="2"]')?.getAttribute("data-tooltip")).toContain("NOVO (30)");
  });
  it("destaque realça só os ids dados e atenua o resto; destacar() troca sem redesenhar", () => {
    const g = dispersao.render(el, pts, { titulo: "t", destaque: new Set(["2"]) });
    expect(el.querySelector('circle[data-id="2"]')?.classList.contains("destaque")).toBe(true);
    expect(el.querySelector('circle[data-id="1"]')?.classList.contains("atenuado")).toBe(true);
    const antes = el.querySelector('circle[data-id="1"]');
    g.destacar(new Set(["1"]));
    expect(el.querySelector('circle[data-id="1"]')).toBe(antes);
    expect(antes?.classList.contains("destaque")).toBe(true);
    g.destacar(new Set());
    expect(el.querySelectorAll("circle.atenuado")).toHaveLength(0);
  });
  it("linha de referência (custo por voto mediano) com rótulo e entrada na tabela", () => {
    dispersao.render(el, pts, { titulo: "t", referencia: { custoPorVoto: 5, rotulo: "Mediana: R$ 5,00 por voto" } });
    const l = el.querySelector("line.referencia") as SVGLineElement;
    expect(l).not.toBeNull();
    expect(Number.isFinite(Number(l.getAttribute("x1")))).toBe(true);
    expect(el.querySelector(".referencia-rotulo")?.textContent).toContain("Mediana");
  });
});

describe("empilhado: hover", () => {
  it("o segmento mostra fonte, valor e % do total da barra", () => {
    empilhado.render(el, [{ rotulo: "Ana", valores: { FEFC: 300, Doações: 100 } }], { titulo: "t" });
    const m = [...el.querySelectorAll("rect.marca")].find((r) => r.getAttribute("aria-label")?.includes("FEFC")) as SVGElement;
    m.dispatchEvent(new MouseEvent("mouseenter", { clientX: 50, clientY: 50 }));
    const b = document.querySelector(".tooltip-flutuante:not([hidden])");
    expect(b?.textContent).toContain("FEFC");
    expect(b?.textContent).toContain("75");
    expect(b?.textContent).toContain("R$");
    m.dispatchEvent(new MouseEvent("mouseleave"));
  });
});

describe("empilhado", () => {
  const dados = [
    { rotulo: "Ana", valores: { "Fundo partidário": 100, "Pessoas físicas": 50 } },
    { rotulo: "Beto", valores: { "Fundo partidário": 0, "Pessoas físicas": 200, Próprios: 10 } },
  ];
  it("um segmento por (candidato, fonte) com valor > 0, legenda e tabela", () => {
    empilhado.render(el, dados, { titulo: "Receita por fonte" });
    expect(el.querySelectorAll("rect.marca")).toHaveLength(4);
    expect(el.querySelectorAll(".legenda-item")).toHaveLength(3);
    expect(tabela(el).querySelectorAll("tbody tr")).toHaveLength(2);
    coresUsadas(el).forEach((c) => { expect(todasCores.has(c.toLowerCase())).toBe(true); });
    expect(el.querySelector("rect.marca")?.getAttribute("aria-label")).toContain("R$");
  });
});

describe("comparação 2022×2026", () => {
  it("um par de pontos e uma linha por item", () => {
    comparacao.render(
      el,
      [
        { rotulo: "SE", antes: 0.02, depois: 0.05 },
        { rotulo: "BA", antes: 0.04, depois: 0.03 },
      ],
      { titulo: "Penetração", rotuloAntes: "2022", rotuloDepois: "2026", formato: (v) => `${(v * 100).toFixed(1)}%` },
    );
    expect(el.querySelectorAll("circle.marca")).toHaveLength(4);
    expect(el.querySelectorAll("line.ligacao")).toHaveLength(2);
    expect(el.querySelectorAll(".legenda-item")).toHaveLength(2);
    expect(tabela(el).querySelectorAll("tbody tr")).toHaveLength(2);
    const alta = el.querySelector("line.ligacao")?.getAttribute("class");
    expect(alta).toContain("alta");
  });
});

describe("pequenos múltiplos", () => {
  it("um painel por série com mesmo domínio", () => {
    multiplos.render(
      el,
      [
        { titulo: "SE", dados: [{ rotulo: "x", valor: 10 }] },
        { titulo: "BA", dados: [{ rotulo: "x", valor: 40 }] },
      ],
      { titulo: "Votos por UF" },
    );
    expect(el.querySelectorAll(".painel")).toHaveLength(2);
    const w = [...el.querySelectorAll("rect.marca")].map((m) => Number(m.getAttribute("width")));
    expect((w[1] ?? 0) / (w[0] ?? 1)).toBeCloseTo(4, 5);
  });
});

describe("revisão T-W03", () => {
  const dispers = [{ id: "1", rotulo: "Ana", custo: 1000, votos: 500 }, { id: "2", rotulo: "Beto", custo: 100000, votos: 20000 }];
  const barra = [{ rotulo: "A", valor: 1 }, { rotulo: "B", valor: 2 }];
  const emp = [{ rotulo: "Ana", valores: { FEFC: 100, PF: 50 } }];
  const comp = [{ rotulo: "Ana", antes: 0.01, depois: 0.02 }];
  const mult = [{ titulo: "2022", dados: barra }, { titulo: "2026", dados: barra }];
  const casos: [string, (c: HTMLElement) => { atualizar: (d: never) => void }, unknown][] = [
    ["barras", (c) => barras.render(c, barra, { titulo: "t" }), barra],
    ["dispersão", (c) => dispersao.render(c, dispers, { titulo: "t" }), dispers],
    ["empilhado", (c) => empilhado.render(c, emp, { titulo: "t" }), emp],
    ["comparação", (c) => comparacao.render(c, comp, { titulo: "t", rotuloAntes: "a", rotuloDepois: "d" }), comp],
    ["múltiplos", (c) => multiplos.render(c, mult, { titulo: "t" }), mult],
  ];
  it.each(casos)("%s: atualizar não duplica svg, details nem marcas", (_n, fazer, dados) => {
    const g = fazer(el);
    const contar = (): number[] => [el.querySelectorAll("svg.grafico").length, el.querySelectorAll("details").length, el.querySelectorAll(".marca").length];
    const antes = contar();
    g.atualizar(dados as never);
    g.atualizar(dados as never);
    expect(contar()).toEqual(antes);
  });
  it.each(casos)("%s: atualizar preserva <details> aberto e o foco na marca", (_n, fazer, dados) => {
    const g = fazer(el);
    document.body.append(el);
    el.querySelector("details")?.setAttribute("open", "");
    const marcas = [...el.querySelectorAll<SVGElement>(".marca")];
    marcas[1 % marcas.length]?.focus();
    const idx = marcas.indexOf(document.activeElement as SVGElement);
    g.atualizar(dados as never);
    expect(el.querySelector("details")?.hasAttribute("open")).toBe(true);
    if (idx >= 0) expect(document.activeElement).toBe(el.querySelectorAll(".marca")[idx]);
  });
  it("empilhado: negativos (estornos) não entram no total nem passam do eixo", () => {
    empilhado.render(el, [{ rotulo: "Ana", valores: { FEFC: 100, PF: -40 } }], { titulo: "t" });
    expect(el.querySelectorAll("rect.marca")).toHaveLength(1);
    expect(tabela(el).querySelector("tbody tr")?.textContent).toContain("R$ 100,00");
    const r = el.querySelector("rect.marca");
    expect(Number(r?.getAttribute("x")) + Number(r?.getAttribute("width"))).toBeLessThanOrEqual(640 - 20 + 0.001);
  });
  it("empilhado: mais de 7 fontes agrupa o excedente em 'Outras' sem lançar", () => {
    const valores = Object.fromEntries(Array.from({ length: 10 }, (_, i) => [`F${String(i)}`, 10]));
    const g = empilhado.render(el, [{ rotulo: "Ana", valores }], { titulo: "t" });
    expect(() => { g.atualizar([{ rotulo: "Ana", valores }]); }).not.toThrow();
    const itens = [...el.querySelectorAll(".legenda-item")].map((l) => l.textContent);
    expect(itens).toHaveLength(7);
    expect(itens.at(-1)).toBe("Outras");
    expect(tabela(el).textContent).toContain("R$ 100,00"); // total preservado
  });
  it("empilhado: a cor de uma fonte não muda com a ordem dos dados quando 'fontes' é fixa", () => {
    const fontes = ["FEFC", "PF"];
    const cor = (dados: Parameters<typeof empilhado.render>[1]): string | null => {
      empilhado.render(el, dados, { titulo: "t", fontes });
      return [...el.querySelectorAll("rect.marca")].find((r) => r.getAttribute("aria-label")?.includes("PF"))?.getAttribute("fill") ?? null;
    };
    const a = cor([{ rotulo: "A", valores: { FEFC: 1, PF: 2 } }]);
    const b = cor([{ rotulo: "A", valores: { PF: 2 } }]);
    expect(a).not.toBeNull();
    expect(a).toBe(b);
  });
  it("eixos usam compacto pt-BR (mil/mi), não '1.5k'", () => {
    expect(formatarCompacto(1500)).not.toMatch(/k/i);
    expect(formatarCompacto(1500)).toMatch(/mil/);
    dispersao.render(el, dispers, { titulo: "t" });
    expect(el.querySelector("g.eixo-x")?.textContent).not.toMatch(/\dk|\d\.\dk/);
  });
});

describe("ranking: nomes completos (T-W10)", () => {
  it("quebrarLinhas divide em palavras sem perder texto", async () => {
    const { quebrarLinhas } = await import("../../src/componentes/graficos/barras");
    const nome = "MARIA APARECIDA DE OLIVEIRA DOS SANTOS";
    const l = quebrarLinhas(nome, 18);
    expect(l.length).toBeGreaterThan(1);
    expect(l.join(" ")).toBe(nome);
    expect(Math.max(...l.map((x) => x.length))).toBeLessThanOrEqual(18);
    expect(quebrarLinhas("CURTO", 18)).toEqual(["CURTO"]);
  });
  it("palavra maior que o limite não é cortada", async () => {
    const { quebrarLinhas } = await import("../../src/componentes/graficos/barras");
    expect(quebrarLinhas("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 10)).toEqual(["ABCDEFGHIJKLMNOPQRSTUVWXYZ"]);
  });
  it("o rótulo do nome mais longo aparece inteiro no SVG e a barra mostra tooltip rico", async () => {
    const { render } = await import("../../src/componentes/graficos/ranking");
    const c = document.createElement("div");
    document.body.append(c);
    const longo = "FULANO DE TAL BEZERRA DE MENEZES FILHO";
    render(c, [{ rotulo: longo, valor: 10, detalhe: [["Nome civil", "Fulano Bezerra"], ["Partido", "MISSAO"]] }, { rotulo: "ANA", valor: 5 }], { titulo: "t" });
    expect((c.querySelector("svg")?.textContent ?? "").replace(/\s+/g, " ")).toContain(longo.split(" ")[0]);
    const tspans = [...c.querySelectorAll("svg text.rotulo tspan")].map((t) => t.textContent).join(" ");
    expect(tspans).toContain("MENEZES FILHO");
    expect(c.querySelector(".marca")?.getAttribute("data-tooltip")).toContain("Partido");
  });
});
