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
    expect(svg?.getAttribute("role")).toBe("img");
    expect(svg?.getAttribute("aria-label")).toContain("Votos por município");
    const marcas = el.querySelectorAll("rect.marca");
    expect(marcas).toHaveLength(3);
    marcas.forEach((m) => {
      expect(m.getAttribute("tabindex")).toBe("0");
      expect(m.getAttribute("aria-label")).toMatch(/: /);
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
    expect(w[1]! / w[0]!).toBeCloseTo(2.5, 5);
  });
  it("usa só cores das paletas", () => {
    barras.render(el, dados, { titulo: "t" });
    coresUsadas(el).forEach((c) => expect(todasCores.has(c.toLowerCase())).toBe(true));
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
  });
  it("lista vazia e só zeros não quebram", () => {
    dispersao.render(el, [], { titulo: "t" });
    expect(el.textContent).toContain("Sem dados");
    dispersao.render(el, [{ id: "z", rotulo: "Z", custo: 0, votos: 0 }], { titulo: "t" });
    expect(el.querySelectorAll("circle.marca")).toHaveLength(1);
  });
  it("foco por teclado nos pontos", () => {
    dispersao.render(el, pontos, { titulo: "t" });
    el.querySelectorAll("circle.marca").forEach((m) => expect(m.getAttribute("tabindex")).toBe("0"));
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
    coresUsadas(el).forEach((c) => expect(todasCores.has(c.toLowerCase())).toBe(true));
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
    expect(w[1]! / w[0]!).toBeCloseTo(4, 5);
  });
});
