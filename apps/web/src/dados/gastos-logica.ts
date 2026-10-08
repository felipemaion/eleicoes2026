/** Lógica pura da tela de gastos: junta gasto × candidatura e prepara o que o gráfico e o tooltip mostram. */
import type { PontoCustoVoto } from "../componentes/graficos/dispersao";
import { formatarMoeda, formatarNumero, formatarPontos } from "../formato";
import type { RespostaGastos } from "./contrato";

const semAcento = (s: string): string => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Um ponto por candidato com gasto; partido, resultado e % público vêm do próprio `/gastos`. */
export function pontosDeGastos(g: RespostaGastos, base: "contratado" | "pago"): PontoCustoVoto[] {
  return g.por_candidato.map((c) => {
    const custo = base === "contratado" ? c.custo.despesa_contratada : c.custo.despesa_paga;
    const cpv = base === "contratado" ? c.custo.custo_voto_contratado : c.custo.custo_voto_pago;
    return {
      id: String(c.sq_candidato), rotulo: c.nm_urna, votos: c.custo.votos, custo,
      detalhe: [
        ["Partido", `${c.partido.sigla} (${String(c.partido.numero)})`],
        ["UF", c.sg_uf],
        ["Cargo", c.cargo.toLowerCase()],
        ["Votos", formatarNumero(c.custo.votos)],
        ["Despesa contratada", formatarMoeda(c.custo.despesa_contratada)],
        ["Despesa paga", formatarMoeda(c.custo.despesa_paga)],
        [`Custo por voto (${base})`, cpv === null ? "sem votos" : formatarMoeda(cpv)],
        ["% recursos públicos", c.pct_publico === null ? "indisponível" : formatarPontos(c.pct_publico)],
        ["Resultado", c.resultado?.toLowerCase() ?? "ainda não definido"],
      ],
    };
  });
}

/** Mediana de custo ÷ votos entre quem tem custo e votos positivos; a linha de referência do gráfico. */
export function medianaCustoVoto(pontos: readonly PontoCustoVoto[]): number | null {
  const r = pontos.filter((p) => p.custo > 0 && p.votos > 0).map((p) => p.custo / p.votos).sort((a, b) => a - b);
  if (r.length === 0) return null;
  const m = Math.floor(r.length / 2);
  return r.length % 2 ? (r[m] ?? null) : (((r[m - 1] ?? 0) + (r[m] ?? 0)) / 2);
}

/** Ids dos pontos cujo nome contém a consulta (sem acento/caixa). Consulta vazia não destaca nada. */
export function idsQueCasam(pontos: readonly PontoCustoVoto[], consulta: string): Set<string> {
  const q = semAcento(consulta.trim());
  if (q === "") return new Set();
  return new Set(pontos.filter((p) => semAcento(p.rotulo).includes(q)).map((p) => p.id));
}
