/**
 * Critério de "n baixo" (docs/metodologia/indicadores.md §1.4): `E = aptos × taxa_referência < 20`,
 * com a taxa de referência da UF (votos ÷ aptos somados). A API de mapa ainda não manda a marca,
 * então o front a deriva do que já recebe; o resultado é só visual (hachura), nunca altera valores.
 */
export const LIMIAR_N_BAIXO = 20;

export interface BaseNBaixo {
  votos: number;
  eleitorado: number;
}

/** Os 2 primeiros dígitos do código IBGE são a UF; valem para município ("2800308") e zona ("2800308-12"). */
const ufDaChave = (id: string): string => id.slice(0, 2);

export function marcarNBaixo(base: Readonly<Record<string, BaseNBaixo>>): Record<string, boolean> {
  const somas = new Map<string, { votos: number; aptos: number }>();
  for (const [id, d] of Object.entries(base)) {
    const s = somas.get(ufDaChave(id)) ?? { votos: 0, aptos: 0 };
    s.votos += d.votos;
    s.aptos += d.eleitorado;
    somas.set(ufDaChave(id), s);
  }
  return Object.fromEntries(
    Object.entries(base).map(([id, d]) => {
      const s = somas.get(ufDaChave(id));
      const taxa = s && s.aptos > 0 ? s.votos / s.aptos : 0;
      return [id, d.eleitorado === 0 || d.eleitorado * taxa < LIMIAR_N_BAIXO] as const;
    }),
  );
}
