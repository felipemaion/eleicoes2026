/** Fonte única de cores do dashboard: paletas de dados e temas de interface. */

/** ColorBrewer Blues (7) — sequencial para taxas (penetração). */
const sequencial = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#084594"] as const;
/** ColorBrewer PuOr (7) — divergente seguro para daltônicos; neutro no índice 3 (swing=0, LQ=1). */
const divergente = ["#b35806", "#f1a340", "#fee0b6", "#f7f7f7", "#d8daeb", "#998ec3", "#542788"] as const;
/** Okabe-Ito (8) — categórica segura para daltônicos. */
const categorica = ["#000000", "#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7"] as const;

export const PALETAS = { sequencial, divergente, categorica } as const;

export type Tema = {
  readonly fundo: string;
  readonly superficie: string;
  readonly texto: string;
  readonly textoSuave: string;
  readonly borda: string;
  readonly destaque: string;
  /** Áreas sem dado no mapa/legenda: cinza neutro, fora da escala de dados. */
  readonly semDado: string;
};

export const TEMAS = {
  claro: { fundo: "#ffffff", superficie: "#f4f6f8", texto: "#1a1d21", textoSuave: "#4a5360", borda: "#c9d0d8", destaque: "#084594", semDado: "#c3c9d0" },
  escuro: { fundo: "#121417", superficie: "#1c2025", texto: "#eceff1", textoSuave: "#aab4be", borda: "#39414a", destaque: "#9ecae1", semDado: "#4b535c" },
} as const satisfies Record<string, Tema>;

function luminancia(hex: string): number {
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

/** CSS das variáveis de cor, gerado dos temas para não duplicar valores em tokens.css. */
export function cssDasCores(): string {
  return (
    `:root{${variaveis(TEMAS.claro)}color-scheme:light dark}` +
    `@media (prefers-color-scheme:dark){:root:not([data-tema="claro"]){${variaveis(TEMAS.escuro)}}}` +
    `:root[data-tema="escuro"]{${variaveis(TEMAS.escuro)}}`
  );
}
