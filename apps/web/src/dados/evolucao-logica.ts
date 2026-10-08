/** Lógica pura da seleção de candidatos na Evolução 2022×2026 (sem DOM, sem fetch). */
import type { PessoaEvolucao } from "./contrato";

export const MAX_PESSOAS = 50;
const ID_PESSOA = /^[0-9a-f]{12}$/;

/** `a,b,c` da URL → ids válidos, únicos, até o limite da API (o valor vai parar na query string). */
export function parsePessoas(bruto: string): string[] {
  const vistos = new Set<string>();
  for (const x of bruto.split(",")) if (ID_PESSOA.test(x)) vistos.add(x);
  return [...vistos].slice(0, MAX_PESSOAS);
}

export function alternarPessoa(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id].slice(0, MAX_PESSOAS);
}

/** Query de `/comparativo` por seleção: `pessoas` repetido; o cargo é obrigatório na API. */
export function paramsPessoas(ids: readonly string[], cargo: string, uf: string): Record<string, string | string[]> {
  return { cargo, ...(uf !== "BR" ? { uf } : {}), pessoas: [...ids] };
}

export const soIndicados = (itens: readonly PessoaEvolucao[]): PessoaEvolucao[] => itens.filter((p) => p.de.indicado || p.para.indicado);

/** Só quem entra no comparativo (mesmo cargo nos dois anos, fora o Senado). */
export const idsDe = (itens: readonly PessoaEvolucao[]): string[] => itens.filter((p) => p.comparavel).map((p) => p.pessoa_id_publico);

export interface LinhaComparativa {
  id: string;
  nome: string;
  cargo_de: string;
  cargo_para: string;
  partido_de: string;
  partido_para: string;
  uf_para: string;
  votos_de: number;
  votos_para: number;
  delta_votos: number;
  penetracao_de: number | null;
  penetracao_para: number | null;
  delta_penetracao: number | null;
  comparavel: boolean;
}

export type ColunaOrdenavel = keyof Omit<LinhaComparativa, "id" | "comparavel">;
export type Sentido = "asc" | "desc";
export type Penetracoes = Readonly<Record<string, { de: number | null; para: number | null }>>;

/** Penetração vem à parte (ficha de cada ano): desconhecida é `null`, nunca zero. */
export function linhasComparativas(itens: readonly PessoaEvolucao[], pen: Penetracoes): LinhaComparativa[] {
  return itens.map((p) => {
    const x = pen[p.pessoa_id_publico];
    const de = x?.de ?? null;
    const para = x?.para ?? null;
    return {
      id: p.pessoa_id_publico, nome: p.nome, comparavel: p.comparavel,
      cargo_de: p.de.cargo, cargo_para: p.para.cargo,
      partido_de: p.de.partido.sigla, partido_para: p.para.partido.sigla, uf_para: p.para.uf,
      votos_de: p.de.votos, votos_para: p.para.votos, delta_votos: p.para.votos - p.de.votos,
      penetracao_de: de, penetracao_para: para, delta_penetracao: de === null || para === null ? null : para - de,
    };
  });
}

/** Ordena por coluna; valores ausentes ficam sempre no fim, qualquer que seja o sentido. */
export function ordenarLinhas(linhas: readonly LinhaComparativa[], coluna: ColunaOrdenavel, sentido: Sentido): LinhaComparativa[] {
  const f = sentido === "asc" ? 1 : -1;
  return [...linhas].sort((a, b) => {
    const x = a[coluna];
    const y = b[coluna];
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "pt-BR")) * f;
  });
}
