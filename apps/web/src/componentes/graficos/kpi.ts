import { formatarMoeda, formatarNumero, formatarPercentual, formatarPermil, formatarPontos } from "../../formato";
import type { Grafico } from "./base";

export interface Kpi {
  rotulo: string;
  valor: number;
  /** "percentual" recebe fração (0,05); "pontos" recebe 0–100; "permil" recebe ‰. */
  formato: "inteiro" | "moeda" | "percentual" | "permil" | "pontos";
  /** Ex.: "% dos votos válidos" — vai junto do valor para não deixar o número solto. */
  unidade?: string;
  /** Chave de ajuda (indicador); a tela decide o que desenhar via `opcoes.ajuda`. */
  ajuda?: string;
  /** Chave de procedência; a tela decide o que desenhar via `opcoes.fonte`. */
  fonte?: string;
}

export interface OpcoesKpi {
  /** Nó do "?" para a chave; o componente não conhece os textos públicos. */
  ajuda?: (chave: string) => Node;
  /** Nó do "fonte" para a chave. */
  fonte?: (chave: string) => Node;
}

const FORMATOS = { inteiro: formatarNumero, moeda: formatarMoeda, percentual: formatarPercentual, permil: formatarPermil, pontos: formatarPontos } as const;

/** Cartões de indicador. Texto puro (`<dl>`): já é acessível, dispensa tabela alternativa. */
export function render(container: HTMLElement, dados: readonly Kpi[], opcoes: OpcoesKpi = {}): Grafico<readonly Kpi[]> {
  function atualizar(novos: readonly Kpi[]): void {
    const lista = document.createElement("dl");
    lista.className = "kpis";
    for (const k of novos) {
      const cartao = document.createElement("div");
      cartao.className = "kpi";
      const dt = document.createElement("dt");
      dt.textContent = k.rotulo;
      if (k.ajuda !== undefined && opcoes.ajuda) dt.append(" ", opcoes.ajuda(k.ajuda));
      if (k.fonte !== undefined && opcoes.fonte) dt.append(" ", opcoes.fonte(k.fonte));
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
