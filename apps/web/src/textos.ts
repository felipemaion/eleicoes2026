/**
 * Textos públicos (tooltips "?", avisos, rodapés, glossário). Fonte única:
 * `docs/metodologia/publico/textos.json` — escrito pelo analista, importado no build (nada é
 * redigido aqui). Este módulo só escolhe QUAIS textos cada tela mostra e preenche placeholders.
 */
import bruto from "../../../docs/metodologia/publico/textos.json";
import type { Tela } from "./store";

/** Telas com texto público próprio ("Como ler" é a página dos textos, não tem subtítulo/rodapé). */
export type TelaComTextos = Exclude<Tela, "como-ler">;

interface IndicadorTexto { titulo: string; resumo: string; como_ler: string; unidade: string; denominador: string; cuidado: string; fonte: string }
interface AvisoTexto { titulo: string; texto: string; nivel: "atencao" | "info" }
interface TelaTexto { titulo: string; subtitulo: string; nota_rodape: string; indicadores: string[]; avisos: string[] }
interface Termo { termo: string; definicao: string }
interface Textos {
  indicadores: Record<string, IndicadorTexto>;
  avisos: Record<string, AvisoTexto>;
  telas: Record<string, TelaTexto>;
  glossario: Record<string, Termo>;
}
const T = bruto as unknown as Textos;

export interface Contexto {
  /** `DT_GERACAO` do TSE, como a API devolve (data ou data-hora ISO). */
  dt_geracao?: string | undefined;
  /** Mês-base do IPCA (`base_ipca` da API, AAAA-MM). */
  mes_base_ipca?: string | undefined;
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function formatarDtGeracao(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(iso);
  if (!m) throw new Error(`dt_geracao inválida: "${iso}"`);
  const data = `${m[3] ?? ""}/${m[2] ?? ""}/${m[1] ?? ""}`;
  return m[4] === undefined ? data : `${data} ${m[4]}:${m[5] ?? "00"}`;
}

export function formatarMesBase(aaaamm: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(aaaamm);
  const nome = m ? MESES[Number(m[2]) - 1] : undefined;
  if (!m || !nome) throw new Error(`mês-base inválido: "${aaaamm}" (esperado AAAA-MM)`);
  return `${nome}/${m[1] ?? ""}`;
}

const INDISPONIVEL = "indisponível";

/** Troca `{dt_geracao}` e `{mes_base_ipca}`; dado ausente vira "indisponível" (visível), não chave crua. */
export function preencher(texto: string, c: Contexto): string {
  return texto
    .replaceAll("{dt_geracao}", c.dt_geracao === undefined ? INDISPONIVEL : formatarDtGeracao(c.dt_geracao))
    .replaceAll("{mes_base_ipca}", c.mes_base_ipca === undefined ? INDISPONIVEL : formatarMesBase(c.mes_base_ipca));
}

const chaveDaTela = (t: TelaComTextos): string => t.replace(/-/g, "_");
function daTela(t: TelaComTextos): TelaTexto {
  const x = T.telas[chaveDaTela(t)];
  if (!x) throw new Error(`Sem textos públicos para a tela "${t}"`);
  return x;
}

export function indicadorDe(chave: string, c: Contexto): IndicadorTexto {
  const i = T.indicadores[chave];
  if (!i) throw new Error(`Indicador sem texto público: "${chave}"`);
  return { ...i, unidade: preencher(i.unidade, c), cuidado: preencher(i.cuidado, c), como_ler: preencher(i.como_ler, c) };
}

export function definicaoDe(chave: string): Termo {
  const t = T.glossario[chave];
  if (!t) throw new Error(`Termo sem definição no glossário: "${chave}"`);
  return t;
}

export const subtituloDaTela = (t: TelaComTextos): string => daTela(t).subtitulo;
export const notaRodape = (t: TelaComTextos, c: Contexto): string => preencher(daTela(t).nota_rodape, c);

export interface Aviso extends AvisoTexto { chave: string }
export interface ContextoAvisos extends Contexto { contas_parciais?: boolean }

/** `n_baixo` fala de áreas hachuradas, que o mapa ainda não desenha: não prometer o que não existe. */
const AINDA_SEM_RECURSO = new Set(["n_baixo"]);

export function avisosDaTela(t: TelaComTextos, c: ContextoAvisos): Aviso[] {
  return daTela(t).avisos
    .filter((k) => !AINDA_SEM_RECURSO.has(k))
    .filter((k) => (k === "contas_parciais" ? c.contas_parciais === true : k === "ipca" ? c.mes_base_ipca !== undefined : true))
    .map((chave) => {
      const a = T.avisos[chave];
      if (!a) throw new Error(`Aviso sem texto público: "${chave}"`);
      return { chave, ...a, texto: preencher(a.texto, c) };
    });
}
