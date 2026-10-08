/**
 * Lógica pura do comparador 2022×2026 (sem DOM, sem fetch): cada lado é um grupo da
 * configuração ou uma lista de candidaturas (`sq_candidato`). O estado vive na URL.
 */
import type { Params } from "./cliente";

/** Candidaturas por lado: a query string e os chips do cartão não comportam mais. */
export const MAX_POR_LADO = 10;
const SQ_VALIDO = /^\d{1,12}$/;
const GRUPO_VALIDO = /^[a-z0-9_]{1,64}$/;

export type Lado = { tipo: "grupo"; id: string } | { tipo: "candidatos"; sqs: string[] };
/** `null` = o usuário não escolheu: vale o padrão da configuração. */
export type LadoEscolhido = Lado | null;

export interface LadosResolvidos { de: Lado; para: Lado }
export interface ComparacaoConfig { id: string; de: string; para: string; rotulo: string }
export interface GrupoConfig { id: string; rotulo: string; ano: number }

/** `g:<grupo>` ou `c:<sq>,<sq>`; qualquer outra coisa (inclusive vazio) é "sem escolha". */
export function parseLado(bruto: string): LadoEscolhido {
  if (bruto.startsWith("g:")) {
    const id = bruto.slice(2);
    return GRUPO_VALIDO.test(id) ? { tipo: "grupo", id } : null;
  }
  if (bruto.startsWith("c:")) {
    const sqs = [...new Set(bruto.slice(2).split(",").filter((x) => SQ_VALIDO.test(x)))].slice(0, MAX_POR_LADO);
    return sqs.length > 0 ? { tipo: "candidatos", sqs } : null;
  }
  return null;
}

export function formatarLado(lado: LadoEscolhido): string {
  if (lado === null) return "";
  return lado.tipo === "grupo" ? `g:${lado.id}` : `c:${lado.sqs.join(",")}`;
}

export function alternarCandidato(sqs: readonly string[], sq: string): string[] {
  if (sqs.includes(sq)) return sqs.filter((x) => x !== sq);
  return sqs.length >= MAX_POR_LADO ? [...sqs] : [...sqs, sq];
}

/** Comparação configurada que termina no grupo filtrado; sem ela, a primeira declarada. */
function comparacaoPadrao(comparacoes: readonly ComparacaoConfig[], grupo: string): ComparacaoConfig | undefined {
  return comparacoes.find((c) => c.para === grupo) ?? comparacoes[0];
}

/** Lado não escolhido herda o padrão; sem nenhuma comparação configurada o grupo do filtro vale para 2026. */
export function resolverLados(de: LadoEscolhido, para: LadoEscolhido, comparacoes: readonly ComparacaoConfig[], grupoDoFiltro: string): LadosResolvidos {
  const padrao = comparacaoPadrao(comparacoes, grupoDoFiltro);
  return {
    de: de ?? { tipo: "grupo", id: padrao?.de ?? "" },
    para: para ?? { tipo: "grupo", id: padrao?.para ?? grupoDoFiltro },
  };
}

/**
 * Query de `/comparativo`. Dois grupos de uma comparação declarada usam o atalho `comparacao`;
 * o resto vai por lado (`grupo_AAAA` ou `sq_AAAA`), o que permite misturar grupo e candidatos.
 */
export function paramsComparativo(de: Lado, para: Lado, cargo: string, uf: string, comparacoes: readonly ComparacaoConfig[]): Params {
  const base: Record<string, string | string[]> = { cargo, ...(uf !== "BR" ? { uf } : {}) };
  if (de.tipo === "grupo" && para.tipo === "grupo") {
    const c = comparacoes.find((x) => x.de === de.id && x.para === para.id);
    if (c) return { ...base, comparacao: c.id };
  }
  const lado = (l: Lado, ano: "2022" | "2026"): Record<string, string | string[]> => (l.tipo === "grupo" ? { [`grupo_${ano}`]: l.id } : { [`sq_${ano}`]: [...l.sqs] });
  return { ...base, ...lado(de, "2022"), ...lado(para, "2026") };
}

/** Texto curto do que o lado contém: rótulo do grupo ou nomes dos candidatos. */
export function nomeDoLado(lado: Lado, grupos: readonly GrupoConfig[], nomes: ReadonlyMap<string, string>): string {
  if (lado.tipo === "grupo") return grupos.find((g) => g.id === lado.id)?.rotulo ?? lado.id;
  const rotulos = lado.sqs.map((sq) => nomes.get(sq) ?? `candidato ${sq}`);
  if (rotulos.length <= 3) return rotulos.join(" + ");
  return `${rotulos.slice(0, 3).join(", ")} e mais ${String(rotulos.length - 3)}`;
}

export interface EntradaFrase { de: string; para: string; cargo: string; uf: string; nDe: number | null; nPara: number | null }
export interface Frase { de: string; para: string; contexto: string; contagem: string | null }

const candidaturas = (n: number): string => `${String(n)} ${n === 1 ? "candidatura" : "candidaturas"}`;

/** Peças da frase "Comparando X (2022) com Y (2026) · cargo · UF"; a tela só aplica negrito. */
export function fraseResumo(e: EntradaFrase): Frase {
  const contagem = e.nDe !== null && e.nPara !== null ? `${candidaturas(e.nDe)} → ${candidaturas(e.nPara)}` : e.nDe !== null ? candidaturas(e.nDe) : e.nPara !== null ? candidaturas(e.nPara) : null;
  return { de: e.de, para: e.para, contexto: `${e.cargo} · ${e.uf}`, contagem };
}
