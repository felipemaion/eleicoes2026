/**
 * Cliente da API. Tipos de resposta vêm de `./contrato` (único módulo a trocar quando o
 * OpenAPI tiver os endpoints). Cada resposta passa por uma checagem de forma mínima: dado
 * malformado falha alto em vez de virar gráfico errado.
 */
import type {
  Ficha, Meta, PontoVoto, RespostaCandidatos, RespostaComparativo, RespostaGastos, RespostaGrupos, RespostaMapa, RespostaMunicipio,
} from "./contrato";

export type { Meta } from "./contrato";
/** Cancelamento por abort não é falha: quem cancelou já não quer a resposta. */
export function foiCancelada(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export type Params = Readonly<Record<string, string | undefined>>;

export interface ClienteApi {
  meta(sinal?: AbortSignal): Promise<Meta>;
  grupos(sinal?: AbortSignal): Promise<RespostaGrupos>;
  candidatos(p: Params, sinal?: AbortSignal): Promise<RespostaCandidatos>;
  ficha(ano: number, sq: string, sinal?: AbortSignal): Promise<Ficha>;
  mapa(p: Params, sinal?: AbortSignal): Promise<RespostaMapa>;
  pontos(p: Params, sinal?: AbortSignal): Promise<{ pontos: PontoVoto[] }>;
  gastos(p: Params, sinal?: AbortSignal): Promise<RespostaGastos>;
  comparativo(p: Params, sinal?: AbortSignal): Promise<RespostaComparativo>;
  municipio(ibge: string, sinal?: AbortSignal): Promise<RespostaMunicipio>;
}

function ehObjeto(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function ehMeta(x: unknown): x is Meta {
  if (!ehObjeto(x)) return false;
  return typeof x["dt_geracao"] === "string" && Array.isArray(x["anos"]) && Array.isArray(x["ufs"]) && Array.isArray(x["grupos"]);
}

/** Cria o guarda que exige um objeto com estas chaves. */
// T só aparece no predicado de tipo, que é o ponto: o chamador escolhe o tipo da resposta.
// eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
function comChaves<T>(...chaves: string[]): (x: unknown) => x is T {
  return (x): x is T => ehObjeto(x) && chaves.every((k) => k in x);
}

function query(p: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== "") q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function criarCliente(base = "/api"): ClienteApi {
  // T aparece no guarda e no retorno; o linter não enxerga o predicado de tipo como uso.
   
  async function obter<T>(caminho: string, valido: (x: unknown) => x is T, sinal?: AbortSignal): Promise<T> {
    const r = await fetch(`${base}${caminho}`, sinal ? { signal: sinal } : undefined);
    if (!r.ok) throw new Error(`GET ${base}${caminho} falhou: ${String(r.status)}`);
    const corpo: unknown = await r.json();
    if (!valido(corpo)) throw new Error(`GET ${base}${caminho.split("?")[0] ?? caminho}: resposta inesperada`);
    return corpo;
  }
  return {
    meta: (sinal) => obter("/meta", ehMeta, sinal),
    grupos: (sinal) => obter("/grupos", comChaves<RespostaGrupos>("grupos"), sinal),
    candidatos: (p, sinal) => obter(`/candidatos${query(p)}`, comChaves<RespostaCandidatos>("candidatos"), sinal),
    ficha: (ano, sq, sinal) => obter(`/candidatos/${String(ano)}/${encodeURIComponent(sq)}`, comChaves<Ficha>("candidato", "votos_municipios", "gastos", "receitas"), sinal),
    mapa: (p, sinal) => obter(`/mapa${query(p)}`, comChaves<RespostaMapa>("valores", "detalhes", "escala_sugerida", "unidade", "denominador"), sinal),
    pontos: (p, sinal) => obter(`/mapa/pontos${query(p)}`, comChaves<{ pontos: PontoVoto[] }>("pontos"), sinal),
    gastos: (p, sinal) => obter(`/gastos${query(p)}`, comChaves<RespostaGastos>("candidatos", "mes_base_deflator"), sinal),
    comparativo: (p) => obter(`/comparativo${query(p)}`, comChaves<RespostaComparativo>("municipios", "candidatos", "mes_base_deflator")),
    municipio: (ibge, sinal) => obter(`/municipios/${encodeURIComponent(ibge)}`, comChaves<RespostaMunicipio>("cd_mun_ibge", "grupos"), sinal),
  };
}
