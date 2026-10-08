/** Adaptadores puros: resposta da API → entrada dos componentes. Sem DOM, sem fetch. */
import { escalaDivergente, escalaLog, escalaQuantil, validarCoropletico, type Escala, type MetaIndicador } from "../componentes/escalas/escalas";
import type { Barra } from "../componentes/graficos/barras";
import type { ParAntesDepois } from "../componentes/graficos/comparacao";
import type { PontoCustoVoto } from "../componentes/graficos/dispersao";
import type { ReceitaPorFonte } from "../componentes/graficos/empilhado";
import type { Kpi } from "../componentes/graficos/kpi";
import type { DetalheLocal } from "../componentes/mapa/tooltip";
import type { Filtros } from "../store";
import type { Candidato, Ficha, KpisGrupo, RespostaComparativo, RespostaGastos, RespostaMapa } from "./contrato";

/** Filtros → query string da API. "BR" e "todos" são o padrão da API: não vão na URL. */
export function paramsDeFiltros(f: Readonly<Filtros>): Record<string, string> {
  const q: Record<string, string> = { ano: String(f.ano), grupo: f.grupo };
  if (f.uf !== "BR") q["uf"] = f.uf;
  if (f.cargo !== "todos") q["cargo"] = f.cargo;
  return q;
}

/** KPIs da spec §8.1. KPI sem dado some: nunca vira "0" que pareça medição. */
export function kpisDoGrupo(k: KpisGrupo): Kpi[] {
  const lista: Kpi[] = [
    { rotulo: "Votação do partido", valor: k.votos, formato: "inteiro", unidade: `votos (${nf(k.votos_nominais)} nominais + ${nf(k.votos_legenda)} de legenda)` },
    { rotulo: "Penetração", valor: k.penetracao, formato: "percentual", unidade: `% dos aptos${k.penetracao_comparada === null ? "" : ` — MBL 2022: ${pf(k.penetracao_comparada)}`}` },
    { rotulo: "% dos válidos", valor: k.pct_validos, formato: "percentual", unidade: "% dos votos válidos" },
    { rotulo: "Eleitos / candidaturas aptas", valor: k.eleitos, formato: "inteiro", unidade: `de ${nf(k.candidaturas_aptas)} candidaturas aptas` },
  ];
  if (k.custo_voto_contratado !== null) lista.push({ rotulo: "Custo por voto contratado", valor: k.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos nominais" });
  lista.push({ rotulo: "% recursos públicos", valor: k.pct_publico, formato: "percentual", unidade: "FEFC + Fundo Partidário ÷ receitas" });
  if (k.delta_penetracao !== null) lista.push({ rotulo: "Δ penetração vs MBL 2022", valor: k.delta_penetracao, formato: "percentual", unidade: "pontos percentuais dos aptos, mesmo cargo" });
  return lista;
}

const nf = (v: number): string => new Intl.NumberFormat("pt-BR").format(v);
const pf = (v: number): string => new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

export function rankingDeCandidatos(cs: readonly Candidato[], soIndicados: boolean): Barra[] {
  return cs
    .filter((c) => !soIndicados || c.indicado)
    .sort((a, b) => b.votos - a.votos)
    .map((c) => ({ rotulo: c.nome, valor: c.votos }));
}

export function dispersaoCustoVoto(g: RespostaGastos, base: "contratado" | "pago"): PontoCustoVoto[] {
  return g.candidatos.map((c) => ({ id: c.id, rotulo: c.rotulo, votos: c.votos, custo: base === "contratado" ? c.custo_contratado : c.custo_pago }));
}

export function receitaEmpilhada(g: RespostaGastos): ReceitaPorFonte[] {
  return g.receita_por_fonte.map((r) => ({ rotulo: r.rotulo, valores: r.valores }));
}

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
export function mesPorExtenso(aaaamm: string): string {
  const [a, m] = aaaamm.split("-");
  const nome = MESES[Number(m) - 1];
  if (!a || !nome) throw new Error(`Mês-base inválido: "${aaaamm}" (esperado AAAA-MM)`);
  return `${nome} de ${a}`;
}

/** Avisos obrigatórios de leitura dos gastos. */
export function avisosGastos(g: Pick<RespostaGastos, "contas_parciais" | "mes_base_deflator">): string[] {
  const a: string[] = [];
  if (g.contas_parciais) a.push("Contas de 2026 parciais: candidatos ainda podem prestar contas; custo por voto tende a mudar.");
  a.push(`Valores de 2022 deflacionados pelo IPCA para ${mesPorExtenso(g.mes_base_deflator)}.`);
  return a;
}

export interface MapaPronto {
  escala: Escala;
  meta: MetaIndicador;
  valores: Record<string, number>;
  detalhes: Record<string, DetalheLocal>;
}

function extensaoSimetrica(valores: readonly number[]): number {
  const m = Math.max(0, ...valores.map(Math.abs));
  if (m === 0) return 1;
  const p = 10 ** Math.floor(Math.log10(m));
  return Math.ceil(m / p) * p;
}

export function escalaDoMapa(r: RespostaMapa): MapaPronto {
  const meta: MetaIndicador = { nome: r.unidade, tipo: r.tipo, unidade: r.unidade, denominador: r.denominador };
  validarCoropletico(meta);
  const v = Object.values(r.valores);
  const escala =
    r.escala_sugerida === "divergente" ? escalaDivergente({ extensao: r.extensao ?? extensaoSimetrica(v) })
    : r.escala_sugerida === "log" ? escalaLog({ fatorMaximo: 4 })
    : escalaQuantil(v);
  const detalhes = Object.fromEntries(
    Object.entries(r.detalhes).map(([id, d]) => [id, { nome: d.nome ?? id, votos: d.votos, taxa: d.taxa, eleitorado: d.aptos }]),
  );
  return { escala, meta, valores: r.valores, detalhes };
}

/** Quebras calculadas sobre 2022 ∪ 2026: o mesmo azul significa o mesmo valor nos dois mapas. */
export function escalaIgualNosDoisAnos(antes: Readonly<Record<string, number>>, depois: Readonly<Record<string, number>>): { antes: Escala; depois: Escala } {
  const e = escalaQuantil([...Object.values(antes), ...Object.values(depois)]);
  return { antes: e, depois: e };
}

export function mapaDeDiferenca(c: RespostaComparativo): MapaPronto {
  const valores = Object.fromEntries(c.municipios.map((m) => [m.cd_mun_ibge, m.delta_penetracao]));
  const meta: MetaIndicador = {
    nome: "Δ penetração",
    tipo: "diferenca",
    unidade: "Δ penetração (2026 − 2022), fração dos aptos",
    denominador: "eleitores aptos do município (municípios agregados por AMC)",
  };
  validarCoropletico(meta);
  const detalhes = Object.fromEntries(c.municipios.map((m) => [m.cd_mun_ibge, { nome: m.nome, taxa: m.delta_penetracao }]));
  return { escala: escalaDivergente({ extensao: extensaoSimetrica(Object.values(valores)) }), meta, valores, detalhes };
}

export function paresDaComparacao(c: RespostaComparativo): ParAntesDepois[] {
  return c.candidatos.map((x) => ({ rotulo: x.rotulo, antes: x.antes, depois: x.depois }));
}

export function barrasMunicipios(f: Ficha, topo: number): Barra[] {
  return [...f.votos_municipios].sort((a, b) => b.votos - a.votos).slice(0, topo).map((m) => ({ rotulo: m.nome, valor: m.votos }));
}
