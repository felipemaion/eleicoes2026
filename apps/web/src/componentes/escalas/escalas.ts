/**
 * Escalas D3 → classes discretas. Fonte única de cor: a mesma escala gera a expressão do
 * MapLibre e a legenda SVG, então mapa e legenda nunca divergem.
 */
import { scaleLinear, scaleLog, scaleQuantile, scaleThreshold } from "d3";
import { PALETAS } from "../../paletas";

export type TipoIndicador = "taxa" | "razao" | "diferenca" | "absoluto";

export interface MetaIndicador {
  nome: string;
  tipo: TipoIndicador;
  /** Ex.: "% dos votos válidos". */
  unidade: string;
  /** Ex.: "votos válidos do município". */
  denominador: string;
}

export class ErroCoropleticoAbsoluto extends Error {
  constructor(nome: string) {
    super(`"${nome}" é um valor absoluto: coroplético só aceita taxas. Use símbolos proporcionais (definirPontos) ou hexbin.`);
    this.name = "ErroCoropleticoAbsoluto";
  }
}

/** Falha alto se o indicador não pode ir num coroplético ou se faltar unidade/denominador. */
export function validarCoropletico(meta: MetaIndicador): void {
  if (meta.tipo === "absoluto") throw new ErroCoropleticoAbsoluto(meta.nome);
  if (meta.unidade.trim() === "") throw new Error(`Indicador "${meta.nome}" sem unidade: a legenda exige unidade.`);
  if (meta.denominador.trim() === "") throw new Error(`Indicador "${meta.nome}" sem denominador: a legenda exige denominador.`);
}

export interface Escala {
  readonly tipo: "quantil" | "limiar" | "divergente" | "log";
  /** Limites inferiores das classes 1..n-1 (estritamente crescentes). */
  readonly quebras: readonly number[];
  readonly cores: readonly string[];
  /** Valor neutro (0 para swing, 1 para LQ); ausente nas escalas sequenciais. */
  readonly centro?: number;
  readonly corSemDado: string;
  /** Índice da classe (0..n-1); -1 se não houver dado. */
  classe(valor: number | null | undefined): number;
  cor(valor: number | null | undefined): string;
}

const COR_SEM_DADO = "#d9d9d9";

function criar(tipo: Escala["tipo"], quebras: readonly number[], cores: readonly string[], centro?: number): Escala {
  for (let i = 1; i < quebras.length; i++) {
    if (!((quebras[i] ?? 0) > (quebras[i - 1] ?? 0))) throw new Error("As quebras devem ser estritamente crescentes.");
  }
  if (cores.length !== quebras.length + 1) throw new Error(`Esperadas ${String(quebras.length + 1)} cores para ${String(quebras.length)} quebras; recebidas ${String(cores.length)}.`);
  const indice = scaleThreshold().domain([...quebras]).range(cores.map((_, i) => i));
  const classe = (v: number | null | undefined): number => (v === null || v === undefined || Number.isNaN(v) ? -1 : indice(v));
  return {
    tipo,
    quebras,
    cores,
    ...(centro === undefined ? {} : { centro }),
    corSemDado: COR_SEM_DADO,
    classe,
    cor: (v) => cores[classe(v)] ?? COR_SEM_DADO,
  };
}

/** Sequencial por quantis dos próprios dados. Quebras repetidas (muitos zeros) reduzem as classes. */
export function escalaQuantil(valores: readonly number[], cores: readonly string[] = PALETAS.sequencial): Escala {
  const validos = valores.filter((v) => Number.isFinite(v));
  if (validos.length === 0) throw new Error("escalaQuantil: sem valores.");
  const brutas = scaleQuantile<string>().domain(validos).range([...cores]).quantiles();
  const quebras = [...new Set(brutas)];
  return criar("quantil", quebras, cores.slice(0, quebras.length + 1));
}

/** Quebras fixas — use para aplicar as MESMAS quebras a 2022 e 2026. */
export function escalaLimiar(quebras: readonly number[], cores: readonly string[]): Escala {
  return criar("limiar", quebras, cores);
}

function quebrasSimetricas(n: number, gerar: (t: number) => number): number[] {
  return Array.from({ length: n - 1 }, (_, k) => gerar((k + 1) / n));
}

/** Divergente linear centrada em `centro` (0 para swing), simétrica até ±`extensao`. */
export function escalaDivergente(o: { extensao: number; centro?: number; cores?: readonly string[] }): Escala {
  const { extensao, centro = 0, cores = PALETAS.divergente } = o;
  if (!(extensao > 0)) throw new Error("escalaDivergente: extensao deve ser > 0.");
  const s = scaleLinear().domain([0, 1]).range([centro - extensao, centro + extensao]);
  return criar("divergente", quebrasSimetricas(cores.length, s), cores, centro);
}

/** Divergente em log centrada em 1 (LQ): LQ=2 e LQ=0,5 ficam equidistantes do neutro. */
export function escalaLog(o: { fatorMaximo: number; cores?: readonly string[] }): Escala {
  const { fatorMaximo, cores = PALETAS.divergente } = o;
  if (!(fatorMaximo > 1)) throw new Error("escalaLog: fatorMaximo deve ser > 1.");
  const s = scaleLog().domain([1 / fatorMaximo, fatorMaximo]).range([0, 1]);
  return criar("log", quebrasSimetricas(cores.length, (t) => s.invert(t)), cores, 1);
}

export type Expressao = readonly unknown[];

/** Expressão MapLibre (`case`+`step`) a partir da escala; valor vem do feature-state por padrão. */
export function expressaoCor(escala: Escala, valor: Expressao = ["feature-state", "valor"]): Expressao {
  const [primeira = COR_SEM_DADO, ...demais] = escala.cores;
  const passos: (string | number)[] = [];
  demais.forEach((cor, i) => { passos.push(escala.quebras[i] ?? 0, cor); });
  return ["case", ["!=", ["typeof", valor], "number"], escala.corSemDado, ["step", valor, primeira, ...passos]];
}
