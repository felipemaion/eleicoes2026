import { formatarMoeda, formatarNumero, formatarPercentual } from "../../formato";
import type { Grafico } from "./base";

export interface Kpi {
  rotulo: string;
  valor: number;
  formato: "inteiro" | "moeda" | "percentual";
  /** Ex.: "% dos votos válidos" — vai junto do valor para não deixar o número solto. */
  unidade?: string;
}

const FORMATOS = { inteiro: formatarNumero, moeda: formatarMoeda, percentual: formatarPercentual } as const;

/** Cartões de indicador. Texto puro (`<dl>`): já é acessível, dispensa tabela alternativa. */
export function render(container: HTMLElement, dados: readonly Kpi[]): Grafico<readonly Kpi[]> {
  function atualizar(novos: readonly Kpi[]): void {
    const lista = document.createElement("dl");
    lista.className = "kpis";
    for (const k of novos) {
      const cartao = document.createElement("div");
      cartao.className = "kpi";
      const dt = document.createElement("dt");
      dt.textContent = k.rotulo;
      const dd = document.createElement("dd");
      dd.textContent = FORMATOS[k.formato](k.valor);
      cartao.append(dt, dd);
      if (k.unidade !== undefined) {
        // <dd> extra: <small> solto dentro de <dl> é inválido (axe: definition-list).
        const u = document.createElement("dd");
        u.className = "unidade";
        u.textContent = k.unidade;
        cartao.append(u);
      }
      lista.append(cartao);
    }
    container.replaceChildren(lista);
  }
  atualizar(dados);
  return { atualizar, destruir: () => { container.replaceChildren(); } };
}
