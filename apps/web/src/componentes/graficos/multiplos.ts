import { desenhar, type Barra } from "./barras";
import type { Grafico } from "./base";

export interface Serie {
  titulo: string;
  dados: readonly Barra[];
}

export interface OpcoesMultiplos {
  titulo: string;
  formato?: (v: number) => string;
  largura?: number;
}

/** Um painel de barras por série, todos com o MESMO eixo — sem isso a comparação engana. */
export function render(container: HTMLElement, series: readonly Serie[], opcoes: OpcoesMultiplos): Grafico<readonly Serie[]> {
  function atualizar(novas: readonly Serie[]): void {
    const max = Math.max(0, ...novas.flatMap((s) => s.dados.map((d) => d.valor)));
    const grade = document.createElement("div");
    grade.className = "multiplos";
    grade.setAttribute("role", "group");
    grade.setAttribute("aria-label", `${opcoes.titulo}: ${String(novas.length)} painéis com a mesma escala`);
    for (const s of novas) {
      const painel = document.createElement("figure");
      painel.className = "painel";
      const cap = document.createElement("figcaption");
      cap.textContent = s.titulo;
      const corpo = document.createElement("div");
      desenhar(corpo, s.dados, { titulo: `${opcoes.titulo} — ${s.titulo}`, dominioMax: max, largura: opcoes.largura ?? 360, ...(opcoes.formato ? { formato: opcoes.formato } : {}) });
      painel.append(cap, corpo);
      grade.append(painel);
    }
    container.replaceChildren(grade);
  }
  atualizar(series);
  return { atualizar, destruir: () => { container.replaceChildren(); } };
}
