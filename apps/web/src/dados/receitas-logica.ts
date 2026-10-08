/** Lógica pura das receitas na tela de Financiamento: KPIs, pontos da dispersão e linhas da comparação 2022→2026. */
import type { PontoCustoVoto } from "../componentes/graficos/dispersao";
import type { Kpi } from "../componentes/graficos/kpi";
import { formatarDecimal, formatarMoeda, formatarNumero, formatarPontos } from "../formato";
import type { ComparativoReceitas, RespostaGastos } from "./contrato";

const sinal = (v: number): string => (v > 0 ? "+" : v < 0 ? "−" : "");

/**
 * KPIs de receita do grupo. Cada valor `null` da API (sem contas, sem votos) some: nunca vira zero.
 * A receita do grupo é líquida de repasses internos (§4.6); a chave de ajuda explica isso.
 */
export function kpisDeReceita(g: RespostaGastos): Kpi[] {
  const k: Kpi[] = [];
  const rc = g.receitas;
  const add = (rotulo: string, ajuda: string, valor: number | null | undefined, formato: Kpi["formato"], unidade: string): void => {
    if (valor !== null && valor !== undefined) k.push({ fonte: "contas", rotulo, ajuda, valor, formato, unidade });
  };
  add("Receita total do grupo", "receitas_grupo", rc?.receita_total, "moeda", "R$, líquida de repasses entre membros");
  add("Receita por voto", "receita_por_voto", g.receita_por_voto.receita_por_voto, "moeda", "R$ de receita ÷ votos nominais");
  add("% recursos públicos", "pct_publico", rc?.pct_publico, "pontos", "FEFC + Fundo Partidário ÷ receitas");
  add("% autofinanciamento", "pct_autofinanciamento", rc?.pct_autofinanciamento, "pontos", "recursos próprios ÷ receitas");
  add("% pessoas físicas", "pct_pessoa_fisica", rc?.pct_pessoa_fisica, "pontos", "doações de pessoas + financiamento coletivo ÷ receitas");
  add("Saldo da campanha", "saldo_campanha", g.saldo.saldo_contratado, "moeda", "receita − despesa contratada");
  return k;
}

/** Um ponto por candidato com linha de receita (`null` ≠ zero); o eixo "custo" do gráfico recebe a receita bruta. */
export function pontosDeReceita(g: RespostaGastos): PontoCustoVoto[] {
  const pct = (v: number | null): string => (v === null ? "indisponível" : formatarPontos(v));
  const moeda = (v: number | null, vazio: string): string => (v === null ? vazio : formatarMoeda(v));
  return g.por_candidato.flatMap((c) => {
    if (c.receita_total === null) return [];
    return [{
      id: String(c.sq_candidato), rotulo: c.nm_urna, votos: c.custo.votos, custo: c.receita_total,
      foto: c.foto_url, linkTse: c.link_tse_candidato,
      detalhe: [
        ["Partido", `${c.partido.sigla} (${String(c.partido.numero)})`],
        ["UF", c.sg_uf],
        ["Cargo", c.cargo.toLowerCase()],
        ["Votos", formatarNumero(c.custo.votos)],
        ["Receita total", formatarMoeda(c.receita_total)],
        ["Receita por voto", moeda(c.receita_por_voto, "sem votos")],
        ["Despesa contratada", formatarMoeda(c.custo.despesa_contratada)],
        ["Saldo (receita − despesa contratada)", moeda(c.saldo_contratado, "indisponível")],
        ["% recursos públicos", pct(c.pct_publico)],
        ["% autofinanciamento", pct(c.pct_autofinanciamento)],
        ["% pessoas físicas", pct(c.pct_pessoa_fisica)],
        ["Resultado", c.resultado?.toLowerCase() ?? "ainda não definido"],
      ],
    } satisfies PontoCustoVoto];
  });
}

/** Faixa honesta da receita do grupo quando há repasse de doador desconhecido (§4.6); `null` sem ela. */
export function notaFaixaReceita(g: RespostaGastos): string | null {
  const f = g.receitas?.faixa_receita;
  if (!f) return null;
  return `Há repasses sem doador identificado: a receita do grupo está entre ${formatarMoeda(f.minima)} e ${formatarMoeda(f.maxima)}.`;
}

export interface LinhaComparativoReceita {
  chave: string;
  rotulo: string;
  ajuda: string;
  /** 2022 em R$ do mês-base (ou %), já corrigido pelo IPCA. */
  de: string;
  /** 2022 como o TSE publicou. `null` nos percentuais, em que não há correção. */
  deNominal: string | null;
  para: string;
  variacao: string;
}

const ROTULOS: Readonly<Record<string, string>> = {
  receita_total: "Receita total",
  receita_por_voto: "Receita por voto",
  receita_por_mil_aptos: "Receita por mil eleitores",
  receita_media_candidato: "Receita média por candidato",
  receita_mediana_candidato: "Receita mediana por candidato",
  pct_publico: "% recursos públicos",
  pct_autofinanciamento: "% autofinanciamento",
  pct_pessoa_fisica: "% pessoas físicas",
  pct_estimavel: "% receitas estimáveis",
};
const AJUDAS: Readonly<Record<string, string>> = { receita_por_voto: "receita_por_voto", receita_por_mil_aptos: "receita_por_mil_aptos", receita_media_candidato: "distribuicao_receita", receita_mediana_candidato: "distribuicao_receita", pct_publico: "pct_publico", pct_autofinanciamento: "pct_autofinanciamento", pct_pessoa_fisica: "pct_pessoa_fisica", pct_estimavel: "receitas_estimaveis" };

const rotuloDe = (chave: string): string => ROTULOS[chave] ?? `Receita: ${chave.replace(/^receita_/, "").replace(/_/g, " ")}`;

const SEM_DADO = "indisponível";
const comoMoeda = (v: number | null): string => (v === null ? SEM_DADO : formatarMoeda(v));
const comoPontos = (v: number | null): string => (v === null ? SEM_DADO : formatarPontos(v));

/** Monetários primeiro (R$ do mês-base, variação em %), depois as fatias (variação em pontos percentuais). */
export function linhasDoComparativoReceitas(r: ComparativoReceitas): LinhaComparativoReceita[] {
  const monetarias = Object.entries(r.monetarios).map(([chave, v]): LinhaComparativoReceita => ({
    chave, rotulo: rotuloDe(chave), ajuda: AJUDAS[chave] ?? "comparacao_receitas",
    de: comoMoeda(v.de), deNominal: comoMoeda(v.de_nominal), para: comoMoeda(v.para),
    variacao: v.var_pct === null ? "sem base de comparação" : `${sinal(v.var_pct)}${formatarDecimal(Math.abs(v.var_pct))}%`,
  }));
  const fatias = Object.entries(r.percentuais).map(([chave, v]): LinhaComparativoReceita => ({
    chave, rotulo: rotuloDe(chave), ajuda: AJUDAS[chave] ?? "comparacao_receitas",
    de: comoPontos(v.de), deNominal: null, para: comoPontos(v.para),
    variacao: v.delta === null ? "sem base de comparação" : `${sinal(v.delta)}${formatarDecimal(Math.abs(v.delta))} p.p.`,
  }));
  return [...monetarias, ...fatias];
}
