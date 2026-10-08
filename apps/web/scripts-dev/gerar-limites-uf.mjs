// Gera src/dados/limites-uf.ts a partir de ufs.geojsonl (malha IBGE, mesma fonte dos PMTiles).
// Uso: node scripts-dev/gerar-limites-uf.mjs <ufs.geojsonl>
import { readFileSync, writeFileSync } from "node:fs";

const [entrada] = process.argv.slice(2);
if (!entrada) throw new Error("Informe o caminho de ufs.geojsonl");
const alcancar = (c, caixa) => {
  if (typeof c[0] === "number") {
    caixa[0] = Math.min(caixa[0], c[0]); caixa[1] = Math.min(caixa[1], c[1]);
    caixa[2] = Math.max(caixa[2], c[0]); caixa[3] = Math.max(caixa[3], c[1]);
  } else c.forEach((x) => alcancar(x, caixa));
};
const linhas = readFileSync(entrada, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
const itens = linhas.map((f) => {
  const caixa = [Infinity, Infinity, -Infinity, -Infinity];
  alcancar(f.geometry.coordinates, caixa);
  return [f.properties.cd_uf, f.properties.sg_uf, caixa.map((v) => Math.round(v * 1e4) / 1e4)];
}).sort((a, b) => a[0] - b[0]);
if (itens.length !== 27) throw new Error(`Esperadas 27 UFs, vieram ${itens.length}`);
const corpo = itens.map(([cd, sg, c]) => `  ${cd}: [${c.join(", ")}], // ${sg}`).join("\n");
writeFileSync(new URL("../src/dados/limites-uf.ts", import.meta.url), `// GERADO por scripts-dev/gerar-limites-uf.mjs a partir da malha IBGE — não editar à mão.
import type { Limites } from "../componentes/mapa/geo";

/** Caixa [oeste, sul, leste, norte] de cada UF, indexada pelo código IBGE de 2 dígitos. */
export const LIMITES_UF: Readonly<Record<number, Limites>> = {
${corpo}
};

/** Caixa que envolve as UFs dos ids (município "3550308" ou zona "3550308-7": 2 primeiros dígitos = UF). \`null\` se nenhuma UF é reconhecida. */
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
`);
