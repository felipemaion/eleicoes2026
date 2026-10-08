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
