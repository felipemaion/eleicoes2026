import { beforeEach, describe, expect, it } from "vitest";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "../../src/telas/textos-ui";

beforeEach(() => { document.body.innerHTML = ""; });

describe("ajuda '?'", () => {
  it("botão acessível que abre/fecha o painel com como ler, unidade, denominador e cuidado", () => {
    const el = ajuda("penetracao", {});
    document.body.append(el);
    const botao = el.querySelector("button") as HTMLButtonElement;
    const painel = el.querySelector("[id]") as HTMLElement;
    expect(botao.getAttribute("aria-label")).toMatch(/Ajuda: Penetração/);
    expect(botao.getAttribute("aria-expanded")).toBe("false");
    expect(botao.getAttribute("aria-controls")).toBe(painel.id);
    expect(painel.hidden).toBe(true);
    botao.click();
    expect(painel.hidden).toBe(false);
    expect(botao.getAttribute("aria-expanded")).toBe("true");
    expect(painel.textContent).toMatch(/Unidade/);
    expect(painel.textContent).toMatch(/Denominador/);
    expect(painel.textContent).toMatch(/Cuidado/);
    botao.click();
    expect(painel.hidden).toBe(true);
  });
  it("Esc fecha e devolve o foco ao botão", () => {
    const el = ajuda("penetracao", {});
    document.body.append(el);
    const botao = el.querySelector("button") as HTMLButtonElement;
    botao.click();
    botao.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(botao.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(botao);
  });
  it("ids únicos entre ajudas", () => {
    const a = ajuda("penetracao", {}).querySelector("[id]")?.id;
    const b = ajuda("penetracao", {}).querySelector("[id]")?.id;
    expect(a).not.toBe(b);
  });
});

describe("avisos, cabeçalho e rodapé", () => {
  it("avisos em região rotulada, com o nível de cada um; vazio não gera região", () => {
    const aside = avisosUi("gastos", { contas_parciais: true, dt_geracao: "2026-10-07", mes_base_ipca: "2026-09" }) as HTMLElement;
    expect(aside.getAttribute("aria-label")).toBe("Avisos de leitura");
    expect(aside.textContent).toMatch(/Contas de 2026 parciais/);
    expect(aside.textContent).toMatch(/set\/2026/);
    expect(aside.querySelector("[data-nivel=atencao]")).not.toBeNull();
    expect(avisosUi("gastos", { contas_parciais: false })).toBeNull();
  });
  it("vários avisos: o essencial fica à vista e o resto recolhido em 'Notas sobre os dados (N)'", () => {
    const aside = avisosUi("gastos", { contas_parciais: true, dt_geracao: "2026-10-07", mes_base_ipca: "2026-09" }) as HTMLElement;
    const visiveis = [...aside.children].filter((c) => c.tagName === "P");
    expect(visiveis).toHaveLength(1);
    expect(visiveis[0]?.textContent).toMatch(/Contas de 2026 parciais/);
    const resto = aside.querySelector("details") as HTMLDetailsElement;
    expect(resto.open).toBe(false);
    expect(resto.querySelector("summary")?.textContent).toBe("Notas sobre os dados (1)");
  });
  it("aviso único não ganha recolhimento", () => {
    const aside = avisosUi("gastos", { contas_parciais: true, dt_geracao: "2026-10-07" }) as HTMLElement;
    expect(aside.querySelector("details")).toBeNull();
  });
  it("cabeçalho: subtítulo público da tela", () => {
    expect(cabecalhoDaTela("mapa").textContent).toMatch(/Penetração/);
  });
  it("rodapé traz fonte e data de geração", () => {
    expect(rodapeUi("evolucao", { dt_geracao: "2026-10-07" }).textContent).toMatch(/07\/10\/2026/);
  });
});
