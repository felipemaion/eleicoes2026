/** Fonte única de cores do dashboard: paletas de dados e temas de interface. */

/**
 * Cores oficiais do Partido Missão, lidas do CSS do site oficial (https://missao.org.br, 08/10/2026):
 * amarelo #fcbe26 (também #fbac1e em detalhes) e preto #070d0c. Branco é o #ffffff.
 */
export const OFICIAL_MISSAO = { amarelo: "#fcbe26", preto: "#070d0c", branco: "#ffffff" } as const;

/**
 * Sequencial para taxas: do creme ao âmbar-queimado (claro → escuro = menos → mais), derivado do amarelo da marca.
 * Todas as classes têm ≥ 1,5:1 sobre a superfície do mapa nos dois temas; a ordem de luminância é monotônica.
 */
const sequencial = ["#fff6d1", "#fee9a0", "#fdd35f", "#fcbe26", "#e8970f", "#c9710a", "#a0510a"] as const;
/** Divergente: âmbar (abaixo do esperado) ↔ azul (acima), neutro creme no índice 3 (swing=0, LQ=1). Seguro p/ daltônicos. */
const divergente = ["#7a4300", "#c9710a", "#fcbe26", "#f4f1e8", "#a9c4dc", "#4f86b8", "#1f5385"] as const;
/** Okabe-Ito (8) — categórica segura para daltônicos. */
const categorica = ["#000000", "#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7"] as const;

export const PALETAS = { sequencial, divergente, categorica } as const;

export type Tema = {
  readonly fundo: string;
  readonly superficie: string;
  /** Superfície elevada (tooltip, cartão em hover). */
  readonly superficieAlta: string;
  readonly texto: string;
  readonly textoSuave: string;
  readonly borda: string;
  /** Acento para linhas, foco e texto de destaque: sempre ≥ 4,5:1 sobre o fundo (amarelo no escuro, âmbar no claro). */
  readonly destaque: string;
  /** Amarelo da marca como preenchimento (botão ativo, selo); o texto sobre ele é `textoAcento`. */
  readonly acento: string;
  readonly textoAcento: string;
  /** Cor das marcas de dados (barras, pontos) nos gráficos. */
  readonly dado: string;
  /** Áreas sem dado no mapa/legenda: cinza neutro, fora da escala de dados. */
  readonly semDado: string;
};

export const TEMAS = {
  claro: { fundo: "#ffffff", superficie: "#f5f3ee", superficieAlta: "#ffffff", texto: "#11161a", textoSuave: "#4d5552", borda: "#cfcac0", destaque: "#8a4f00", acento: "#fcbe26", textoAcento: "#070d0c", dado: "#b86a00", semDado: "#a5a9a6" },
  escuro: { fundo: "#070d0c", superficie: "#121918", superficieAlta: "#1c2523", texto: "#f5f5f2", textoSuave: "#b4bcb8", borda: "#34403d", destaque: "#fcbe26", acento: "#fcbe26", textoAcento: "#070d0c", dado: "#fcbe26", semDado: "#4b5350" },
} as const satisfies Record<string, Tema>;

export function luminancia(hex: string): number {
  const canais = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const [r = 0, g = 0, b = 0] = canais;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Razão de contraste WCAG entre duas cores `#rrggbb`. */
export function contraste(a: string, b: string): number {
  const [maior, menor] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number];
  return (maior + 0.05) / (menor + 0.05);
}

function variaveis(t: Tema): string {
  return Object.entries<string>(t)
    .map(([k, v]) => `--cor-${k.replace(/[A-Z]/g, (m: string) => "-" + m.toLowerCase())}:${v};`)
    .join("");
}

/**
 * CSS das variáveis de cor, gerado dos temas para não duplicar valores em tokens.css.
 * A identidade da marca é escura: o tema claro só entra por escolha explícita (`data-tema="claro"`).
 */
export function cssDasCores(): string {
  return (
    `:root{${variaveis(TEMAS.escuro)}color-scheme:dark}` +
    `:root[data-tema="claro"]{${variaveis(TEMAS.claro)}color-scheme:light}`
  );
}
