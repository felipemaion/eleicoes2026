import { desenhar, type Barra, type OpcoesBarras } from "./barras";
import type { Grafico } from "./base";

export interface OpcoesRanking extends Omit<OpcoesBarras, "prefixo"> {
  /** Quantos itens mostrar (padrão 10). */
  topo?: number;
}

function preparar(dados: readonly Barra[], topo: number): Barra[] {
  return [...dados].sort((a, b) => b.valor - a.valor).slice(0, topo);
}

/** Ranking = barras ordenadas e numeradas; reaproveita o desenho de `barras`. */
export function render(container: HTMLElement, dados: readonly Barra[], opcoes: OpcoesRanking): Grafico<readonly Barra[]> {
  const topo = opcoes.topo ?? 10;
  const desenharRanking = (d: readonly Barra[]): void => { desenhar(container, preparar(d, topo), { ...opcoes, prefixo: (_, i) => `${String(i + 1)}. ` }); };
  desenharRanking(dados);
  return { atualizar: desenharRanking, destruir: () => { container.replaceChildren(); } };
}
