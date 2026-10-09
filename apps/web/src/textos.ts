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
  comparador: { ui: Record<string, string>; nota_grupo: Record<string, string> };
}
const T = bruto as unknown as Textos;

export interface Contexto {
  /** `DT_GERACAO` do TSE, como a API devolve (data ou data-hora ISO). */
  dt_geracao?: string | undefined;
  /** Mês-base do IPCA (`base_ipca` da API, AAAA-MM). */
  mes_base_ipca?: string | undefined;
  /** Momento (ISO, UTC) da coleta mais recente do Instagram; vira a data de Brasília no texto. */
  dt_coleta_redes?: string | undefined;
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

/** DD/MM/AAAA no fuso de Brasília: a coleta é registrada em UTC, e perto da meia-noite o dia muda. */
export function formatarDataBrasilia(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) throw new Error(`data inválida: "${iso}"`);
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

const INDISPONIVEL = "indisponível";

/** Troca `{dt_geracao}` e `{mes_base_ipca}`; dado ausente vira "indisponível" (visível), não chave crua. */
export function preencher(texto: string, c: Contexto): string {
  return texto
    .replaceAll("{dt_geracao}", c.dt_geracao === undefined ? INDISPONIVEL : formatarDtGeracao(c.dt_geracao))
    .replaceAll("{dt_coleta_redes}", c.dt_coleta_redes === undefined ? INDISPONIVEL : formatarDataBrasilia(c.dt_coleta_redes))
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
export interface ContextoAvisos extends Contexto {
  contas_parciais?: boolean;
  /** Ids de aviso que a API de redes mandou; sem a lista, todos os avisos de redes valem. */
  avisos_redes?: readonly string[] | undefined;
  /** O cargo tem 2º turno (presidente, governador): só então o aviso do 2º turno vale. */
  segundo_turno?: boolean;
}

/** Aviso de redes que a API decide (menos o do 2º turno, que depende do cargo). */
const AVISO_REDES_DA_API = (k: string): boolean => k.startsWith("redes_") && k !== "redes_segundo_turno";


export function avisosDaTela(t: TelaComTextos, c: ContextoAvisos): Aviso[] {
  return daTela(t).avisos
    .filter((k) => {
      if (k === "contas_parciais") return c.contas_parciais === true;
      if (k === "ipca") return c.mes_base_ipca !== undefined;
      if (k === "redes_segundo_turno") return c.segundo_turno === true;
      if (AVISO_REDES_DA_API(k)) return c.avisos_redes === undefined || c.avisos_redes.includes(k);
      return true;
    })
    .map((chave) => {
      const a = T.avisos[chave];
      if (!a) throw new Error(`Aviso sem texto público: "${chave}"`);
      return { chave, ...a, texto: preencher(a.texto, c) };
    });
}

// ---- Comparador 2022×2026 (textos.json › comparador) ----
const U = T.comparador.ui;
function ui(chave: string): string {
  const t = U[chave];
  if (t === undefined) throw new Error(`Texto do comparador ausente em textos.json: "${chave}"`);
  return t;
}
const sub = (texto: string, valores: Record<string, string | number>): string =>
  Object.entries(valores).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)), texto);

/** Textos da UI do comparador (pt-BR). Fonte única: `docs/metodologia/publico/textos.json`. */
export const TEXTOS_COMPARADOR = {
  alterar: ui("alterar"),
  aplicar: ui("aplicar"),
  cancelar: ui("cancelar"),
  limpar: ui("limpar"),
  modoRotulo: ui("modo_rotulo"),
  modoGrupo: ui("modo_grupo"),
  modoCandidatos: ui("modo_candidatos"),
  grupoRotulo: ui("grupo_rotulo"),
  buscaRotulo: ui("busca_rotulo"),
  placeholderBusca: ui("placeholder_busca"),
  sugestoesRotulo: ui("sugestoes_rotulo"),
  minimo: ui("minimo"),
  buscando: ui("buscando"),
  buscaIndisponivel: ui("busca_indisponivel"),
  semResultado: (busca: string): string => sub(ui("sem_resultado"), { busca }),
  refine: (n: number, total: number): string => sub(ui("refine"), { n, total }),
  recorte: (contexto: string): string => sub(ui("recorte"), { contexto }),
  erro422: ui("erro_422"),
  erroSqForaGeral: ui("erro_sq_fora_geral"),
  erroSqLado: ui("erro_sq_lado"),
  semDadosComparaveis: ui("sem_dados_comparaveis"),
  seloIndicado: ui("selo_indicado"),
  notaGrupo: T.comparador.nota_grupo as Readonly<Record<string, string>>,
  carregandoNomes: ui("carregando_nomes"),
  notasDados: ui("notas_dados"),
  tabelaTitulo: ui("tabela_titulo"),
} as const;
