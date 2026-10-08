import type { Expressao } from "../escalas/escalas";

const votos: Expressao = ["to-number", ["get", "votos"], 0];

/** Raio do círculo ∝ √votos (área ∝ votos); o maior ponto tem `raioMax` px. */
export function expressaoRaioCirculo(votosMax: number, raioMax: number): Expressao {
  if (!(votosMax > 0)) throw new Error("expressaoRaioCirculo: votosMax deve ser > 0.");
  return ["*", raioMax / Math.sqrt(votosMax), ["sqrt", ["max", 0, votos]]];
}

/** Peso do heatmap normalizado em [0,1] pelo maior ponto. */
export function expressaoPesoCalor(votosMax: number): Expressao {
  if (!(votosMax > 0)) throw new Error("expressaoPesoCalor: votosMax deve ser > 0.");
  return ["min", 1, ["/", votos, votosMax]];
}

/** Remove NaN/±Infinity: no MapLibre cairiam na classe 0 em vez de "sem dado". */
export function soFinitos(valores: Readonly<Record<string, number>>): Record<string, number> {
  return Object.fromEntries(Object.entries(valores).filter(([, v]) => Number.isFinite(v)));
}

/**
 * Opacidade do preenchimento por abrangência: áreas cujo código IBGE começa pelo da UF ficam
 * cheias, as demais esmaecidas. Vale para município ("2800308") e zona ("2800308-12").
 */
export function expressaoOpacidade(propriedadeId: string, codigoUf: string | null, cheia: number, esmaecida: number): Expressao | number {
  if (codigoUf === null) return cheia;
  return ["case", ["==", ["slice", ["to-string", ["get", propriedadeId]], 0, 2], codigoUf], cheia, esmaecida];
}
