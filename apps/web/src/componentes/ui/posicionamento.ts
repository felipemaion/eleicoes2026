/** Posicionamento puro de tooltips: nunca sai da tela, vira para cima quando falta espaço embaixo. */
export interface Ancora { x: number; y: number; largura: number; altura: number }
export interface Medida { largura: number; altura: number }
export interface Viewport { largura: number; altura: number }
export interface Posicao {
  x: number;
  y: number;
  /** Largura final (encolhida se a caixa for maior que a tela). */
  largura: number;
  lado: "cima" | "baixo";
  /** Deslocamento horizontal da seta dentro da caixa, apontando para o centro da âncora. */
  seta: number;
}

const MARGEM = 8;
const FOLGA = 10; // espaço para a seta

export function posicionar(a: Ancora, caixa: Medida, vp: Viewport): Posicao {
  const largura = Math.min(caixa.largura, vp.largura - 2 * MARGEM);
  const centro = a.x + a.largura / 2;
  const x = Math.min(Math.max(centro - largura / 2, MARGEM), vp.largura - MARGEM - largura);
  const cabeEmbaixo = a.y + a.altura + FOLGA + caixa.altura <= vp.altura - MARGEM;
  const cabeEmCima = a.y - FOLGA - caixa.altura >= MARGEM;
  const lado = cabeEmbaixo || !cabeEmCima ? "baixo" : "cima";
  const y = lado === "baixo" ? a.y + a.altura + FOLGA : a.y - FOLGA - caixa.altura;
  const seta = Math.min(Math.max(centro - x, MARGEM), largura - MARGEM);
  return { x, y, largura, lado, seta };
}
