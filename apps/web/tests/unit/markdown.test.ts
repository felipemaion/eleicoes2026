import { describe, expect, it } from "vitest";
import { renderizarMarkdown } from "../../src/markdown";
import readme from "../../../../docs/metodologia/publico/README.md?raw";

function html(md: string): string {
  const d = document.createElement("div");
  d.append(renderizarMarkdown(md));
  return d.innerHTML;
}

describe("renderizarMarkdown", () => {
  it("títulos, parágrafos que continuam na linha seguinte e listas com continuação", () => {
    expect(html("# A\n\nlinha um\nlinha dois\n\n## B\n\n- item 1\n  continua\n- item 2")).toBe(
      "<h2>A</h2><p>linha um linha dois</p><h3>B</h3><ul><li>item 1 continua</li><li>item 2</li></ul>",
    );
  });
  it("o # do documento vira h2 (o h1 é da tela)", () => {
    expect(html("# T\n### S")).toBe("<h2>T</h2><h4>S</h4>");
  });
  it("negrito, itálico e código inline", () => {
    expect(html("a **forte** e *leve* e `cod`")).toBe("<p>a <strong>forte</strong> e <em>leve</em> e <code>cod</code></p>");
  });
  it("tabela com cabeçalho", () => {
    const t = html("| a | b |\n|---|---|\n| 1 | **2** |");
    expect(t).toBe("<table><thead><tr><th scope=\"col\">a</th><th scope=\"col\">b</th></tr></thead><tbody><tr><td>1</td><td><strong>2</strong></td></tr></tbody></table>");
  });
  it("HTML cru no texto vira texto (nada de innerHTML)", () => {
    expect(html("<img src=x onerror=alert(1)>")).toBe("<p>&lt;img src=x onerror=alert(1)&gt;</p>");
  });
  it("link externo vira âncora segura; link relativo do repositório vira só o texto", () => {
    expect(html("[TSE](https://www.tse.jus.br)")).toBe('<p><a href="https://www.tse.jus.br" rel="noopener noreferrer">TSE</a></p>');
    expect(html("[doc](../indicadores.md)")).toBe("<p>doc</p>");
  });
  it("renderiza o README público inteiro sem sobrar marcação crua", () => {
    const d = document.createElement("div");
    d.append(renderizarMarkdown(readme));
    expect(d.querySelector("h2")?.textContent).toBe("Como ler este painel");
    expect(d.textContent).not.toMatch(/\*\*|\]\(|^#/m);
    expect(d.querySelectorAll("table").length).toBeGreaterThan(0);
  });
});
