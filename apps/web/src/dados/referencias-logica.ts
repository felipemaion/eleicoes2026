/** Lógica pura da aba "Comparar com outros partidos": blocos, parâmetros, seleção, células e índices. */
import { formatarMoeda, formatarNumero } from "../formato";
import type { CandidatoRef as CandidatoApi, PerfilRef as PerfilApi } from "./contrato";
import { formatarHash } from "../rotas";
import { CARGOS, FILTROS_PADRAO, UFS, type Cargo, type Uf } from "../store";
import { cargoDaApi } from "./adaptadores";

/** Campos da T-B21 (ainda fora do contrato gerado): opcionais, e a linha só aparece quando a API os enviar. */
export type PerfilRef = PerfilApi & { receita_por_voto?: number | null; despesa_sobre_receita?: number | null };
export type CandidatoRef = Omit<CandidatoApi, "indicadores" | "indices"> & {
  indicadores: PerfilRef;
  indices: PerfilRef | null;
  /** Prestação de contas com sinal de declaração incompleta (T-B21). */
  alerta_declaracao?: boolean | null;
};
export type BlocoId = "presidente" | "deputado_federal" | "deputado_estadual";
export interface Bloco { id: BlocoId; titulo: string; cargoApi: string; comUf: boolean }

export const BLOCOS: readonly Bloco[] = [
  { id: "presidente", titulo: "Presidente", cargoApi: "PRESIDENTE", comUf: false },
  { id: "deputado_federal", titulo: "Dep. federal", cargoApi: "DEPUTADO FEDERAL", comUf: true },
  { id: "deputado_estadual", titulo: "Dep. estadual", cargoApi: "DEPUTADO ESTADUAL", comUf: true },
];

const blocoDe = (id: BlocoId): Bloco => {
  const b = BLOCOS.find((x) => x.id === id);
  if (!b) throw new Error(`Bloco desconhecido: ${id}`);
  return b;
};

/** Chaves de `Perfil` que a tabela mostra. */
export type ChaveIndicador = keyof PerfilRef;

/** `sq` só viaja para deputados: a API recusa (422) destaque fora dos nossos do recorte. */
export function paramsReferencias(bloco: BlocoId, uf: string, sq: string | null): Record<string, string> {
  const b = blocoDe(bloco);
  return { cargo: b.cargoApi, ...(b.comUf ? { uf } : {}), ...(b.comUf && sq !== null ? { sq } : {}) };
}

/** O bloco acompanha o cargo do filtro global quando ele tem referência; senão, Dep. federal. */
export function blocoInicial(cargo: Cargo): BlocoId {
  return cargo === "presidente" || cargo === "deputado_estadual" ? cargo : "deputado_federal";
}

/** "Brasil" não é UF de deputado: o padrão é SP, onde a referência é mais robusta. */
export function ufInicial(uf: Uf): string {
  return uf === "BR" ? "SP" : uf;
}

/** Destacado pela API; sem destaque, o mais votado. */
export function escolherNosso(candidatos: readonly CandidatoRef[]): CandidatoRef | null {
  const destacado = candidatos.find((c) => c.destacado);
  if (destacado) return destacado;
  return candidatos.reduce<CandidatoRef | null>((m, c) => (m === null || c.votos > m.votos ? c : m), null);
}

const semAcento = (s: string): string => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
export const MAX_RESULTADOS_BUSCA = 8;

export function buscarNossos(candidatos: readonly CandidatoRef[], consulta: string): CandidatoRef[] {
  const q = semAcento(consulta.trim());
  if (q.length < 2) return [];
  return candidatos.filter((c) => semAcento(c.nm_urna).includes(q)).slice(0, MAX_RESULTADOS_BUSCA);
}

const dec1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const dec2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dec3 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

interface Def { chave: ChaveIndicador; rotulo: string; texto: string; formato: (v: number) => string; contexto: boolean; indice: boolean; opcional?: boolean }
export const INDICADORES: readonly Def[] = [
  { chave: "votos", rotulo: "Votos", texto: "votos_nominais", formato: formatarNumero, contexto: true, indice: false },
  { chave: "pct_validos", rotulo: "% dos válidos", texto: "pct_validos", formato: (v) => `${dec1.format(v)} %`, contexto: false, indice: true },
  { chave: "penetracao", rotulo: "Penetração (‰ dos aptos)", texto: "penetracao", formato: (v) => `${dec1.format(v)} ‰`, contexto: false, indice: true },
  { chave: "n_municipios", rotulo: "Municípios com voto", texto: "participacao_maiores", formato: formatarNumero, contexto: true, indice: false },
  { chave: "hhi", rotulo: "Concentração (HHI)", texto: "concentracao", formato: (v) => dec3.format(v), contexto: false, indice: true },
  { chave: "n_efetivo_municipios", rotulo: "Municípios efetivos", texto: "concentracao", formato: (v) => dec1.format(v), contexto: true, indice: false },
  { chave: "custo_voto_pago", rotulo: "Custo por voto (despesa paga)", texto: "custo_por_voto", formato: formatarMoeda, contexto: false, indice: true },
  { chave: "receita_por_voto", rotulo: "Receita por voto", texto: "receita_por_voto", formato: formatarMoeda, contexto: false, indice: true, opcional: true },
  { chave: "despesa_sobre_receita", rotulo: "Despesa ÷ receita", texto: "pct_receita_gasta", formato: (v) => dec2.format(v), contexto: false, indice: true, opcional: true },
  { chave: "receita_total", rotulo: "Receita total", texto: "receitas", formato: formatarMoeda, contexto: true, indice: false },
  { chave: "pct_publico", rotulo: "% fundo público", texto: "pct_publico", formato: (v) => `${dec1.format(v)} %`, contexto: false, indice: true },
  { chave: "pct_pessoa_fisica", rotulo: "% pessoa física", texto: "pct_pessoa_fisica", formato: (v) => `${dec1.format(v)} %`, contexto: false, indice: true },
];

export const FORMATO_INDICE = (v: number): string => `${dec1.format(v)}×`;

export interface Celula { texto: string; semDado: boolean; motivo: string }

const defDe = (chave: ChaveIndicador): Def => {
  const d = INDICADORES.find((x) => x.chave === chave);
  if (!d) throw new Error(`Indicador sem definição: ${chave}`);
  return d;
};
const SEM_DADO = "sem dado";

function formatarValor(chave: ChaveIndicador, v: number | null | undefined, motivo = ""): Celula {
  return v === null || v === undefined ? { texto: SEM_DADO, semDado: true, motivo } : { texto: defDe(chave).formato(v), semDado: false, motivo: "" };
}

/** Nulo é "sem dado" (com o motivo da API), nunca zero. */
export const celula = (c: CandidatoRef, chave: ChaveIndicador): Celula => formatarValor(chave, c.indicadores[chave], c.motivos[chave] ?? "");

export interface LinhaTabela {
  chave: ChaveIndicador;
  rotulo: string;
  texto: string;
  contexto: boolean;
  referencia: Celula[];
  mediana: Celula;
  nosso: Celula | null;
}

export function linhasDaTabela(referencia: readonly CandidatoRef[], mediana: PerfilRef, nosso: CandidatoRef | null): LinhaTabela[] {
  // Campo opcional que nenhum candidato trouxe (a API ainda não o envia): sem linha, em vez de uma fileira de "sem dado".
  const presente = (d: Def): boolean => d.opcional !== true || [...referencia, ...(nosso ? [nosso] : [])].some((c) => c.indicadores[d.chave] !== undefined);
  return INDICADORES.filter(presente).map((d) => ({
    chave: d.chave, rotulo: d.rotulo, texto: d.texto, contexto: d.contexto,
    referencia: referencia.map((r) => celula(r, d.chave)),
    mediana: formatarValor(d.chave, mediana[d.chave]),
    nosso: nosso === null ? null : celula(nosso, d.chave),
  }));
}

export interface PontoIndice { chave: string; rotulo: string; valor: number }

/** Só taxas com índice (valor ÷ mediana); votos e receita são tamanho de campanha e ficam na tabela. */
export function pontosDeIndice(nosso: CandidatoRef | null): PontoIndice[] {
  if (nosso?.indices == null) return [];
  const indices = nosso.indices;
  return INDICADORES.flatMap((d) => {
    const v = indices[d.chave];
    return d.indice && v !== null && v !== undefined ? [{ chave: d.chave, rotulo: d.rotulo, valor: v }] : [];
  });
}

/** Link para a ficha de qualquer candidato do quadro (nosso ou de referência). */
export function hashDaFicha(c: CandidatoRef): string {
  const uf = (UFS as readonly string[]).includes(c.sg_uf) ? (c.sg_uf as Uf) : "BR";
  const cargo = CARGOS.find((k) => cargoDaApi(k) === c.cargo.toUpperCase());
  return formatarHash("candidato", { ...FILTROS_PADRAO, uf, ...(cargo ? { cargo } : {}), ano: c.ano === 2022 ? 2022 : 2026, grupo: c.ano === 2022 ? "mbl_2022" : "missao_2026", candidato: `${String(c.ano)}:${String(c.sq_candidato)}` });
}
