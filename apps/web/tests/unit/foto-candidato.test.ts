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

describe("tooltip da dispersão (T-W17)", () => {
  const pts = [{ id: "1", rotulo: "Kim", custo: 405448.51, votos: 520071, foto: "/fotos/2026/250002546642.webp" }];
  const mover = (c: Element, x: number): void => { c.dispatchEvent(new MouseEvent("mousemove", { bubbles: true, clientX: x, clientY: 60 })); };
  it("a foto do tooltip carrega já (eager): o balão some em instantes e um lazy nunca chegaria a carregar", () => {
    const el = document.getElementById("c") as HTMLElement;
    dispersao.render(el, pts, { titulo: "t" });
    const c = el.querySelector("circle.marca") as SVGElement;
    c.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, clientX: 50, clientY: 50 }));
    const img = document.querySelector(".tooltip-flutuante:not([hidden]) img");
    expect(img?.getAttribute("src")).toBe("/fotos/2026/250002546642.webp");
    expect(img?.getAttribute("loading")).toBe("eager");
  });
  it("mover o cursor sobre o mesmo ponto não recria a foto (só reposiciona)", () => {
    const el = document.getElementById("c") as HTMLElement;
    dispersao.render(el, pts, { titulo: "t" });
    const c = el.querySelector("circle.marca") as SVGElement;
    c.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, clientX: 50, clientY: 50 }));
    const antes = document.querySelector(".tooltip-flutuante img");
    mover(c, 55); mover(c, 60);
    expect(document.querySelector(".tooltip-flutuante img")).toBe(antes);
  });
  it("sem <title> nativo no ponto (o tooltip rico o substitui); aria-label permanece", () => {
    const el = document.getElementById("c") as HTMLElement;
    dispersao.render(el, pts, { titulo: "t" });
    const c = el.querySelector("circle.marca") as SVGElement;
    expect(c.querySelector("title")).toBeNull();
    expect(c.getAttribute("aria-label")).toContain("Kim");
  });
  it("foto e título ficam num cabeçalho; a lista de valores vem depois, sem float", () => {
    const d = document.createElement("div");
    d.append(corpoRico({ titulo: "Kim", linhas: [["Partido", "MISSÃO (14)"]], foto: { nome: "Kim", url: "/f.webp" } }));
    const cab = d.querySelector(".tooltip-cabeca");
    expect(cab?.querySelector("img")).not.toBeNull();
    expect(cab?.querySelector(".tooltip-titulo")?.textContent).toBe("Kim");
    expect(cab?.nextElementSibling?.classList.contains("tooltip-lista--dados")).toBe(true);
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
