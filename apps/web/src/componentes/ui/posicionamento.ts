/** Posicionamento puro de tooltips: nunca sai da tela, vira para cima quando falta espaço embaixo. */
export interface Ancora { x: number; y: number; largura: number; altura: number }
export interface Medida { largura: number; altura: number }
export interface Viewport { largura: number; altura: number }
export interface Posicao {
  x: number;
  y: number;
  /** Largura final: a natural da caixa; só menor que ela quando nem a tela inteira a comporta. */
  largura: number;
  /** `true` quando a largura foi reduzida: os rótulos devem quebrar linha (valores seguem inteiros). */
  comprimida: boolean;
  /** `direita`/`esquerda`: só quando não cabe acima nem abaixo (caixa alta); a seta some. */
  lado: "cima" | "baixo" | "direita" | "esquerda";
  /** Deslocamento horizontal da seta dentro da caixa, apontando para o centro da âncora. */
  seta: number;
}

const MARGEM = 8;
const FOLGA = 10; // espaço para a seta

/** Escolhe o lado com espaço (abaixo → acima → direita → esquerda) usando a largura natural da caixa. */
export function posicionar(a: Ancora, caixa: Medida, vp: Viewport): Posicao {
  const largura = Math.min(caixa.largura, vp.largura - 2 * MARGEM);
  const comprimida = largura < caixa.largura;
  const centro = a.x + a.largura / 2;
  const clampX = (v: number): number => Math.min(Math.max(v, MARGEM), vp.largura - MARGEM - largura);
  const clampY = (v: number): number => Math.min(Math.max(v, MARGEM), vp.altura - MARGEM - caixa.altura);
  const cabeEmbaixo = a.y + a.altura + FOLGA + caixa.altura <= vp.altura - MARGEM;
  const cabeEmCima = a.y - FOLGA - caixa.altura >= MARGEM;
  if (!cabeEmbaixo && !cabeEmCima) {
    const espDir = vp.largura - MARGEM - (a.x + a.largura + FOLGA);
    const espEsq = a.x - FOLGA - MARGEM;
    if (espDir >= largura || espEsq >= largura) {
      const direita = espDir >= largura && (espDir >= espEsq || espEsq < largura);
      const x = direita ? a.x + a.largura + FOLGA : a.x - FOLGA - largura;
      return { x, y: clampY(a.y + a.altura / 2 - caixa.altura / 2), largura, comprimida, lado: direita ? "direita" : "esquerda", seta: 0 };
    }
  }
  const lado = cabeEmbaixo || !cabeEmCima ? "baixo" : "cima";
  const x = clampX(centro - largura / 2);
  const y = lado === "baixo" ? a.y + a.altura + FOLGA : a.y - FOLGA - caixa.altura;
  const seta = Math.min(Math.max(centro - x, MARGEM), largura - MARGEM);
  return { x, y, largura, comprimida, lado, seta };
}
