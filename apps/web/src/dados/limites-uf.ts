// GERADO por scripts-dev/gerar-limites-uf.mjs a partir da malha IBGE — não editar à mão.
import type { Limites } from "../componentes/mapa/geo";

/** Caixa [oeste, sul, leste, norte] de cada UF, indexada pelo código IBGE de 2 dígitos. */
export const LIMITES_UF: Readonly<Record<number, Limites>> = {
  11: [-66.8103, -13.693, -59.7794, -7.9759], // RO
  12: [-73.9904, -11.1456, -66.6269, -7.1118], // AC
  13: [-73.8016, -9.818, -56.0976, 2.244], // AM
  14: [-64.8219, -1.579, -58.8955, 5.2718], // RR
  15: [-58.8956, -9.8412, -46.0634, 2.591], // PA
  16: [-54.8747, -1.236, -49.8758, 4.5088], // AP
  17: [-50.7421, -13.4682, -45.6993, -5.1684], // TO
  21: [-48.7552, -10.2507, -41.7967, -1.0525], // MA
  22: [-46.0282, -10.9288, -40.3705, -2.7573], // PI
  23: [-41.4144, -7.8456, -37.2527, -2.7843], // CE
  24: [-38.5821, -6.9747, -34.9685, -4.8314], // RN
  25: [-38.7652, -8.303, -34.7932, -6.0276], // PB
  26: [-41.3583, -9.4829, -32.4079, -3.8455], // PE
  27: [-38.2376, -10.4986, -35.1527, -8.8211], // AL
  28: [-38.2383, -11.5624, -36.3959, -9.515], // SE
  29: [-46.5765, -18.3372, -37.3411, -8.5328], // BA
  31: [-51.0461, -22.9228, -39.8568, -14.2467], // MG
  32: [-41.8747, -21.3011, -39.6678, -17.8944], // ES
  33: [-44.8893, -23.3676, -40.961, -20.7659], // RJ
  35: [-53.1079, -25.3089, -44.1656, -19.7799], // SP
  41: [-54.6191, -26.7171, -48.0235, -22.5163], // PR
  42: [-53.8371, -29.3551, -48.3736, -25.9768], // SC
  43: [-57.5941, -33.7439, -49.7031, -27.0837], // RS
  50: [-58.1664, -24.0682, -50.9244, -17.1714], // MS
  51: [-61.6279, -18.0416, -50.2248, -7.3518], // MT
  52: [-53.2485, -19.4981, -45.9072, -12.3954], // GO
  53: [-48.2818, -16.05, -47.3085, -15.5018], // DF
};

/** Caixa que envolve as UFs dos ids (município "3550308" ou zona "3550308-7": 2 primeiros dígitos = UF). `null` se nenhuma UF é reconhecida. */
export function limitesDosIds(ids: Iterable<string>): Limites | null {
  const ufs = new Set<number>();
  for (const id of ids) ufs.add(Number(id.slice(0, 2)));
  let caixa: Limites | null = null;
  for (const uf of ufs) {
    const l = LIMITES_UF[uf];
    if (!l) continue;
    caixa = caixa ? [Math.min(caixa[0], l[0]), Math.min(caixa[1], l[1]), Math.max(caixa[2], l[2]), Math.max(caixa[3], l[3])] : l;
  }
  return caixa;
}
