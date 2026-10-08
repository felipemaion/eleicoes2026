import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { criarSobreposicao } from "../../src/componentes/ui/sobreposicao";

beforeEach(() => { vi.useFakeTimers(); document.body.replaceChildren(); });
afterEach(() => { vi.useRealTimers(); });

describe("sobreposição de carregamento", () => {
  it("não aparece em respostas < 200 ms (sem piscar)", () => {
    const s = criarSobreposicao(document.body);
    const fim = s.iniciar("Carregando ranking…");
    vi.advanceTimersByTime(150);
    fim();
    vi.advanceTimersByTime(500);
    expect(s.raiz.hidden).toBe(true);
  });
  it("aparece após 200 ms com o texto, role=status e aria-busy na área", () => {
    const area = document.createElement("main");
    document.body.append(area);
    const s = criarSobreposicao(document.body, area);
    const fim = s.iniciar("Carregando mapa…");
    vi.advanceTimersByTime(250);
    expect(s.raiz.hidden).toBe(false);
    expect(s.raiz.getAttribute("role")).toBe("status");
    expect(s.raiz.textContent).toContain("Carregando mapa…");
    expect(area.getAttribute("aria-busy")).toBe("true");
    fim();
    vi.advanceTimersByTime(300);
    expect(s.raiz.hidden).toBe(true);
    expect(area.getAttribute("aria-busy")).toBe("false");
  });
  it("várias cargas simultâneas: só some quando todas terminam; fim duplicado é inofensivo", () => {
    const s = criarSobreposicao(document.body);
    const a = s.iniciar("A");
    const b = s.iniciar("B");
    vi.advanceTimersByTime(250);
    a(); a();
    vi.advanceTimersByTime(300);
    expect(s.raiz.hidden).toBe(false);
    b();
    vi.advanceTimersByTime(300);
    expect(s.raiz.hidden).toBe(true);
  });
});
