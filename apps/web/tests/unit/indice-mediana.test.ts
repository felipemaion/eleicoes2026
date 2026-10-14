import { beforeEach, describe, expect, it } from "vitest";
import * as indice from "../../src/componentes/graficos/indice-mediana";

let el: HTMLElement;
beforeEach(() => { document.body.innerHTML = '<div id="c"></div>'; el = document.getElementById("c") as HTMLElement; });

const dados = [
  { chave: "pct_validos", rotulo: "% dos válidos", valor: 0.1 },
  { chave: "custo_voto_pago", rotulo: "Custo por voto pago", valor: 2.5 },
  { chave: "hhi", rotulo: "Concentração (HHI)", valor: 1 },
] as const;

describe("índice relativo à mediana", () => {
  it("desenha uma barra por indicador, com linha de referência em 1×", () => {
    indice.render(el, dados, { titulo: "Índice", nome: "ANA" });
    expect(el.querySelectorAll("rect.marca")).toHaveLength(3);
    expect(el.querySelectorAll("line.referencia")).toHaveLength(1);
  });
  it("abaixo de 1× vai para a esquerda da linha e acima para a direita; direção também em classe e texto", () => {
    indice.render(el, dados, { titulo: "Índice", nome: "ANA" });
    const [baixo, alto] = [...el.querySelectorAll("rect.marca")];
    const linha = Number(el.querySelector("line.referencia")?.getAttribute("x1"));
    expect(Number(baixo?.getAttribute("x")) + Number(baixo?.getAttribute("width"))).toBeCloseTo(linha, 1);
    expect(Number(alto?.getAttribute("x"))).toBeCloseTo(linha, 1);
    expect(baixo?.classList.contains("abaixo")).toBe(true);
    expect(alto?.classList.contains("acima")).toBe(true);
    expect(el.textContent).toContain("0,1×");
    expect(el.textContent).toContain("2,5×");
  });
  it("tem tabela alternativa e rótulo acessível por marca", () => {
    indice.render(el, dados, { titulo: "Índice", nome: "ANA" });
    expect(el.querySelectorAll("details table tbody tr")).toHaveLength(3);
    expect(el.querySelector("rect.marca")?.getAttribute("aria-label")).toContain("abaixo da mediana");
  });
  it("sem dados: mensagem, sem svg", () => {
    indice.render(el, [], { titulo: "Índice", nome: "ANA" });
    expect(el.querySelector("svg")).toBeNull();
    expect(el.textContent).toContain("Sem dados");
  });
});
