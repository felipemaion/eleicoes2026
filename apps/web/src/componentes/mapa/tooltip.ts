import { formatarInteiro } from "../../formato";

export interface DetalheLocal {
  nome: string;
  votos?: number;
  taxa?: number;
  eleitorado?: number;
}

export interface ConteudoTooltip {
  titulo: string;
  linhas: [rotulo: string, valor: string][];
}

const SEM_DADO = "sem dado";

/** Texto do tooltip: absoluto, taxa e eleitorado. Valor ausente aparece como "sem dado", nunca 0. */
export function textoTooltip(d: DetalheLocal, o: { unidade: string; formatarTaxa: (v: number) => string }): ConteudoTooltip {
  return {
    titulo: d.nome,
    linhas: [
      ["Votos", d.votos === undefined ? SEM_DADO : formatarInteiro(d.votos)],
      [`Taxa (${o.unidade})`, d.taxa === undefined ? SEM_DADO : o.formatarTaxa(d.taxa)],
      ["Eleitorado", d.eleitorado === undefined ? SEM_DADO : formatarInteiro(d.eleitorado)],
    ],
  };
}
