/** Adaptadores puros: resposta da API → entrada dos componentes. Sem DOM, sem fetch. */
import { escalaDivergente, escalaLimiar, escalaQuantil, validarCoropletico, type Escala, type MetaIndicador } from "../componentes/escalas/escalas";
import type { Barra } from "../componentes/graficos/barras";
import type { PontoCustoVoto } from "../componentes/graficos/dispersao";
import type { ReceitaPorFonte } from "../componentes/graficos/empilhado";
import type { Kpi } from "../componentes/graficos/kpi";
import type { DetalheParcial } from "../componentes/mapa/mapa";
import type { Filtros } from "../store";
import { indicadorDe } from "../textos";
import { PALETAS } from "../paletas";
import { marcarNBaixo } from "./n-baixo";
import type { Candidato, CargoApi, Ficha, RespostaCandidatos, RespostaComparativo, RespostaGastos, RespostaMapa } from "./contrato";

/** Chave do filtro (`deputado_federal`) → valor do enum do OpenAPI (`DEPUTADO FEDERAL`). */
export function cargoDaApi(c: Exclude<Filtros["cargo"], "todos">): CargoApi {
  return c.replace(/_/g, " ").toUpperCase() as CargoApi;
}

/** Cargo usado quando o endpoint exige um e o filtro está em "todos". */
export const CARGO_PADRAO: Exclude<Filtros["cargo"], "todos"> = "deputado_federal";

/** Filtros → query string da API. "BR" e "todos" são o padrão da API: não vão na URL. */
export function paramsDeFiltros(f: Readonly<Filtros>): Record<string, string> {
  const q: Record<string, string> = { ano: String(f.ano), grupo: f.grupo };
  if (f.uf !== "BR") q["uf"] = f.uf;
  if (f.cargo !== "todos") q["cargo"] = cargoDaApi(f.cargo);
  return q;
}

/** Como `paramsDeFiltros`, para endpoints em que `cargo` é obrigatório (mapa, comparativo). */
export function paramsComCargo(f: Readonly<Filtros>): Record<string, string> {
  return { ...paramsDeFiltros(f), cargo: cargoDaApi(f.cargo === "todos" ? CARGO_PADRAO : f.cargo) };
}

const nf = (v: number): string => new Intl.NumberFormat("pt-BR").format(v);
const EH_ELEITO = /^ELEITO/i;

/**
 * KPIs que o contrato permite calcular hoje (a API não tem KPI agregado por grupo).
 * Soma só vale com a lista inteira: se `total` > itens, o valor é rotulado como parcial.
 */
export function kpisDoGrupo(l: RespostaCandidatos, g: RespostaGastos): Kpi[] {
  const completa = l.itens.length >= l.total;
  const votos = l.itens.reduce((a, c) => a + c.votos, 0);
  const parcial = completa ? "" : ` — soma de ${nf(l.itens.length)} de ${nf(l.total)} candidaturas`;
  const lista: Kpi[] = [
    { rotulo: "Votação nominal do grupo", ajuda: "votos_nominais", valor: votos, formato: "inteiro", unidade: `votos nominais${parcial}` },
    { rotulo: "Candidaturas", valor: l.total, formato: "inteiro", unidade: "registradas no grupo" },
  ];
  if (l.itens.some((c) => c.resultado !== null)) {
    lista.push({ rotulo: "Eleitos", valor: l.itens.filter((c) => c.resultado !== null && EH_ELEITO.test(c.resultado)).length, formato: "inteiro", unidade: `de ${nf(l.total)} candidaturas` });
  }
  if (g.agregado.custo_voto_contratado !== null) lista.push({ rotulo: "Custo por voto contratado", ajuda: "custo_por_voto", valor: g.agregado.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos nominais" });
  if (g.receitas.pct_publico !== null) lista.push({ rotulo: "% recursos públicos", ajuda: "pct_publico", valor: g.receitas.pct_publico, formato: "pontos", unidade: "FEFC + Fundo Partidário ÷ receitas" });
  return lista;
}

export function rankingDeCandidatos(cs: readonly Candidato[]): Barra[] {
  return [...cs].sort((a, b) => b.votos - a.votos).map((c) => ({
    rotulo: c.nm_urna, valor: c.votos,
    detalhe: [
      ["Partido", `${c.partido.sigla} (${String(c.partido.numero)})`],
      ["UF", c.sg_uf],
      ["Cargo", c.cargo.replace(/_/g, " ").toLowerCase()],
      ...(c.resultado ? [["Resultado", c.resultado.toLowerCase()] as const] : []),
    ],
  }));
}

export function dispersaoCustoVoto(g: RespostaGastos, base: "contratado" | "pago"): PontoCustoVoto[] {
  return g.por_candidato.map((c) => ({
    id: String(c.sq_candidato), rotulo: c.nm_urna, votos: c.custo.votos,
    custo: base === "contratado" ? c.custo.despesa_contratada : c.custo.despesa_paga,
  }));
}

/** Uma barra empilhada com o grupo inteiro: a API entrega receita por categoria já somada. */
export function receitaEmpilhada(g: RespostaGastos): ReceitaPorFonte[] {
  return [{ rotulo: "Total do grupo", valores: g.receitas.por_categoria }];
}

export interface MapaPronto {
  escala: Escala;
  meta: MetaIndicador;
  valores: Record<string, number>;
  detalhes: Record<string, DetalheParcial>;
  /** Aviso do backend (ex.: sem quebras) a mostrar junto da legenda. */
  aviso: string | null;
}

/** `k` cores amostradas da paleta (a legenda tem sempre quebras + 1 classes). */
function amostrar(cores: readonly string[], k: number): string[] {
  const ultima = cores.length - 1;
  return Array.from({ length: k }, (_, i) => cores[k === 1 ? ultima : Math.round((i * ultima) / (k - 1))] ?? "");
}

function extensaoSimetrica(valores: readonly number[]): number {
  const m = Math.max(0, ...valores.map(Math.abs));
  if (m === 0) return 1;
  const p = 10 ** Math.floor(Math.log10(m));
  return Math.ceil(m / p) * p;
}

/** Remove `null`: território sem denominador é "sem dado" (cinza), nunca 0. */
export function soNumeros(v: Readonly<Record<string, number | null>>): Record<string, number> {
  return Object.fromEntries(Object.entries(v).filter((e): e is [string, number] => e[1] !== null));
}

/**
 * Resposta de `/mapa` → escala + metadados. A API sugere as quebras; o front escolhe a cor.
 * Indicador absoluto (`simbolo_proporcional`) não é coroplético: falha alto (use pontos).
 */
export function escalaDoMapa(r: RespostaMapa): MapaPronto {
  if (r.escala_sugerida.tipo === "simbolo_proporcional") {
    throw new Error(`Indicador "${r.indicador}" é absoluto: use símbolos proporcionais, não coroplético.`);
  }
  // Nome e denominador da legenda vêm do texto público do indicador (o da API é uma palavra solta: "aptos").
  const texto = indicadorDe(r.indicador, {});
  const meta: MetaIndicador = { nome: texto.titulo, tipo: "taxa", unidade: r.unidade, denominador: texto.denominador };
  validarCoropletico(meta);
  const valores = soNumeros(r.valores);
  const q = r.escala_sugerida.quebras;
  const escala = q !== null && q.length > 0 ? escalaLimiar(q, amostrar(PALETAS.sequencial, q.length + 1)) : escalaQuantil(Object.values(valores));
  const baixo = marcarNBaixo(Object.fromEntries(Object.entries(r.detalhes).map(([id, d]) => [id, { votos: d.votos, eleitorado: d.aptos }])));
  const detalhes = Object.fromEntries(
    Object.entries(r.detalhes).map(([id, d]) => [id, { votos: d.votos, eleitorado: d.aptos, nBaixo: baixo[id] ?? false, ...(d.taxa === null ? {} : { taxa: d.taxa }) }]),
  );
  return { escala, meta, valores, detalhes, aviso: r.escala_sugerida.aviso ?? null };
}

/** Quebras calculadas sobre 2022 ∪ 2026: o mesmo azul significa o mesmo valor nos dois mapas. */
export function escalaIgualNosDoisAnos(antes: Readonly<Record<string, number>>, depois: Readonly<Record<string, number>>): { antes: Escala; depois: Escala } {
  const e = escalaQuantil([...Object.values(antes), ...Object.values(depois)]);
  return { antes: e, depois: e };
}

const chaveAmc = (cd: number): string => String(cd);

/** Penetração (‰) por AMC nos dois anos, sem os territórios sem dado. */
export function penetracaoDosAnos(c: RespostaComparativo): { antes: Record<string, number>; depois: Record<string, number> } {
  const pegar = (f: (m: RespostaComparativo["municipios"][number]) => number | null): Record<string, number> =>
    Object.fromEntries(c.municipios.flatMap((m) => { const v = f(m); return v === null ? [] : [[chaveAmc(m.cd_amc), v] as const]; }));
  return { antes: pegar((m) => m.penetracao_de), depois: pegar((m) => m.penetracao_para) };
}

export function mapaDeDiferenca(c: RespostaComparativo): MapaPronto {
  const valores = soNumeros(Object.fromEntries(c.municipios.map((m) => [chaveAmc(m.cd_amc), m.delta_penetracao])));
  const meta: MetaIndicador = {
    nome: "Δ penetração",
    tipo: "diferenca",
    unidade: "‰",
    denominador: "eleitores aptos do município (municípios agregados por AMC)",
  };
  validarCoropletico(meta);
  const detalhes = Object.fromEntries(c.municipios.flatMap((m) => (m.delta_penetracao === null ? [] : [[chaveAmc(m.cd_amc), { nome: m.nome, taxa: m.delta_penetracao }] as const])));
  return { escala: escalaDivergente({ extensao: extensaoSimetrica(Object.values(valores)) }), meta, valores, detalhes, aviso: null };
}

export function barrasMunicipios(f: Ficha, topo: number): Barra[] {
  return [...f.votos_por_municipio].sort((a, b) => b.votos - a.votos).slice(0, topo).map((m) => ({ rotulo: m.nome, valor: m.votos }));
}
