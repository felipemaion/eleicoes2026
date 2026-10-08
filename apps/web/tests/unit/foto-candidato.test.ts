import { beforeEach, describe, expect, it, vi } from "vitest";
import { abrirNoTse, avisoLinkTse, iniciais, figuraCandidato } from "../../src/componentes/ui/foto-candidato";
import { corpoRico } from "../../src/componentes/ui/tooltip";
import * as dispersao from "../../src/componentes/graficos/dispersao";
import { pontosDeGastos } from "../../src/dados/gastos-logica";
import gastos from "../fixtures/api/gastos.json";
import { gastosTipados } from "../fixtures/api/tipado";

beforeEach(() => { document.body.innerHTML = '<div id="c"></div>'; });

describe("iniciais", () => {
  it("usa a primeira letra das duas primeiras palavras, ignorando conectivos", () => {
    expect(iniciais("Ana Souza")).toBe("AS");
    expect(iniciais("Maria da Silva Santos")).toBe("MS");
    expect(iniciais("Kim")).toBe("K");
    expect(iniciais("  ")).toBe("?");
  });
});

describe("figuraCandidato", () => {
  it("com foto: img lazy, tamanho fixo, alt com o nome", () => {
    const f = figuraCandidato("Ana Souza", "/fotos/2026/1.webp");
    const img = f.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/fotos/2026/1.webp");
    expect(img?.getAttribute("loading")).toBe("lazy");
    expect(img?.getAttribute("alt")).toBe("Foto de Ana Souza");
    expect(img?.getAttribute("width")).toBe("80");
    expect(img?.getAttribute("height")).toBe("100");
  });
  it("sem foto (null): placeholder com iniciais, sem <img>, mesmo tamanho", () => {
    const f = figuraCandidato("Bruno Lima", null);
    expect(f.querySelector("img")).toBeNull();
    expect(f.textContent).toBe("BL");
    expect(f.getAttribute("role")).toBe("img");
    expect(f.getAttribute("aria-label")).toBe("Sem foto de Bruno Lima");
  });
});

describe("avisoLinkTse", () => {
  it("convida ao clique e, se não verificado, acrescenta a nota", () => {
    expect(avisoLinkTse({ url: "u", verificado: true, nota: null })).toEqual(["Clique para abrir no TSE (nova aba)."]);
    expect(avisoLinkTse({ url: "u", verificado: false, nota: "padrão a conferir" })).toEqual(["Clique para abrir no TSE (nova aba).", "Link não verificado: padrão a conferir"]);
  });
});

describe("abrirNoTse", () => {
  it("abre em nova aba com noopener,noreferrer", () => {
    const abrir = vi.spyOn(window, "open").mockReturnValue(null);
    abrirNoTse("https://divulgacandcontas.tse.jus.br/x");
    expect(abrir).toHaveBeenCalledWith("https://divulgacandcontas.tse.jus.br/x", "_blank", "noopener,noreferrer");
    abrir.mockRestore();
  });
  it("recusa URL que não seja https", () => {
    const abrir = vi.spyOn(window, "open").mockReturnValue(null);
    abrirNoTse("javascript:alert(1)");
    expect(abrir).not.toHaveBeenCalled();
    abrir.mockRestore();
  });
});

describe("corpoRico com foto", () => {
  it("coloca a figura antes do título e o aviso no rodapé", () => {
    const f = corpoRico({ titulo: "Ana", linhas: [["Votos", "1"]], foto: { nome: "Ana", url: "/fotos/2026/1.webp" }, rodape: ["Clique"] });
    const div = document.createElement("div");
    div.append(f);
    expect(div.querySelector("img")).not.toBeNull();
    expect(div.querySelector(".tooltip-rodape")?.textContent).toContain("Clique");
  });
});

describe("pontosDeGastos propaga foto e link", () => {
  it("foto_url e link_tse_candidato vão para o ponto", () => {
    const pts = pontosDeGastos(gastosTipados(gastos), "contratado");
    expect(pts[0]?.foto).toBe("/fotos/2026/1.webp");
    expect(pts[0]?.linkTse?.url).toContain("divulgacandcontas");
  });
});

describe("dispersão: clique e Enter abrem o TSE", () => {
  const pts = [{ id: "1", rotulo: "Ana", custo: 1000, votos: 500, foto: null, linkTse: { url: "https://divulgacandcontas.tse.jus.br/a", verificado: true, nota: null } },
    { id: "2", rotulo: "Beto", custo: 2000, votos: 900 }];
  it("clique no círculo e Enter no foco chamam window.open; sem link, nada acontece", () => {
    const abrir = vi.spyOn(window, "open").mockReturnValue(null);
    const el = document.getElementById("c") as HTMLElement;
    dispersao.render(el, pts, { titulo: "t" });
    const ana = el.querySelector('circle[data-id="1"]') as SVGElement;
    ana.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    ana.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(abrir).toHaveBeenCalledTimes(2);
    expect(abrir).toHaveBeenCalledWith("https://divulgacandcontas.tse.jus.br/a", "_blank", "noopener,noreferrer");
    (el.querySelector('circle[data-id="2"]') as SVGElement).dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(abrir).toHaveBeenCalledTimes(2);
    expect(ana.getAttribute("role")).toBe("link");
    abrir.mockRestore();
  });
  it("o tooltip mostra a foto (placeholder se null) e o convite ao clique", () => {
    const el = document.getElementById("c") as HTMLElement;
    dispersao.render(el, pts, { titulo: "t" });
    (el.querySelector('circle[data-id="1"]') as SVGElement).dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, clientX: 50, clientY: 50 }));
    const balao = document.querySelector(".tooltip-flutuante:not([hidden])");
    expect(balao?.textContent).toContain("Clique para abrir no TSE");
    expect(balao?.querySelector(".foto-candidato")?.textContent).toBe("A");
  });
});
