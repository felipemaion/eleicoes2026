import { describe, expect, it, vi } from "vitest";
import { criarGerenciadorDeTelas } from "../../src/telas/ciclo";
import { FILTROS_PADRAO, type Estado, type Tela as Chave } from "../../src/store";
import type { Tela } from "../../src/telas/tipos";

const estado = (tela: Chave): Estado => ({ tela, filtros: { ...FILTROS_PADRAO } });

describe("gerenciador de telas", () => {
  it("chama o dispose da renderização anterior antes da próxima, inclusive ao trocar de tela", () => {
    const ordem: string[] = [];
    const fabrica = (nome: string): Tela => ({
      titulo: nome,
      render() {
        ordem.push(`render ${nome}`);
        return () => ordem.push(`dispose ${nome}`);
      },
    });
    const g = criarGerenciadorDeTelas(document.createElement("main"), {
      "visao-geral": fabrica("a"), mapa: fabrica("b"), gastos: fabrica("c"), evolucao: fabrica("d"), candidato: fabrica("e"), "como-ler": fabrica("f"),
    });
    g.desenhar(estado("visao-geral"));
    g.desenhar(estado("visao-geral"));
    g.desenhar(estado("mapa"));
    expect(ordem).toEqual(["render a", "dispose a", "render a", "dispose a", "render b"]);
    g.destruir();
    expect(ordem.at(-1)).toBe("dispose b");
  });

  it("destruir é idempotente", () => {
    const dispose = vi.fn();
    const t: Tela = { titulo: "t", render: () => dispose };
    const g = criarGerenciadorDeTelas(document.createElement("main"), { "visao-geral": t, mapa: t, gastos: t, evolucao: t, candidato: t, "como-ler": t });
    g.desenhar(estado("mapa"));
    g.destruir();
    g.destruir();
    expect(dispose).toHaveBeenCalledTimes(1);
  });
});
