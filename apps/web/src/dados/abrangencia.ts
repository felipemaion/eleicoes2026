/** Região em que um candidato disputa: o mapa enquadra e esmaece o resto a partir dela. */
import type { Limites } from "../componentes/mapa/geo";
import { formatarNumero } from "../formato";
import type { Abrangencia } from "./contrato";
import { LIMITES_UF } from "./limites-uf";

/** Código IBGE de 2 dígitos de cada UF (prefixo dos códigos de município e zona). */
export const CODIGO_UF: Readonly<Record<string, string>> = {
  RO: "11", AC: "12", AM: "13", RR: "14", PA: "15", AP: "16", TO: "17", MA: "21", PI: "22", CE: "23", RN: "24", PB: "25", PE: "26", AL: "27",
  SE: "28", BA: "29", MG: "31", ES: "32", RJ: "33", SP: "35", PR: "41", SC: "42", RS: "43", MS: "50", MT: "51", GO: "52", DF: "53",
};

/** `null` = país inteiro (o mapa volta ao enquadramento do Brasil). */
export function limitesDaAbrangencia(a: Abrangencia): Limites | null {
  if (a.tipo === "pais" || a.uf === null) return null;
  const cod = CODIGO_UF[a.uf];
  return cod === undefined ? null : (LIMITES_UF[Number(cod)] ?? null);
}

export function codigoDaAbrangencia(a: Abrangencia): string | null {
  return a.tipo === "uf" && a.uf !== null ? (CODIGO_UF[a.uf] ?? null) : null;
}

interface CandidaturaMapa { ano: number; sq_candidato: number; cargo: string; abrangencia: Abrangencia }

/** Query do /mapa de UM candidato: ano, cargo e UF vêm dele — os filtros da tela podem ser de outro recorte. */
export function paramsMapaDoCandidato(c: CandidaturaMapa): Record<string, string> {
  return {
    ano: String(c.ano), cargo: c.cargo, sq_candidato: String(c.sq_candidato), indicador: "penetracao", nivel: "municipio",
    ...(c.abrangencia.tipo === "uf" && c.abrangencia.uf !== null ? { uf: c.abrangencia.uf } : {}),
  };
}

/** Votos que não têm município (exterior): informados à parte para o total não parecer errado. */
export function textoForaDoMapa(votos: number): string | null {
  return votos > 0 ? `Votos no exterior: ${formatarNumero(votos)} (fora do mapa).` : null;
}
