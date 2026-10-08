import { formatarDecimal, formatarMoeda, formatarNumero, formatarPercentual, formatarPermil, formatarPontos } from "../../formato";
import type { Grafico } from "./base";

export interface Kpi {
  rotulo: string;
  valor: number;
  /** "percentual" recebe fração (0,05); "pontos" recebe 0–100; "permil" recebe ‰; "decimal" é número com até 2 casas. */
  formato: "inteiro" | "moeda" | "percentual" | "permil" | "pontos" | "decimal";
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

const FORMATOS = { inteiro: formatarNumero, moeda: formatarMoeda, percentual: formatarPercentual, permil: formatarPermil, pontos: formatarPontos, decimal: formatarDecimal } as const;

/** Cartões de indicador. Texto puro (`<dl>`): já é acessível, dispensa tabela alternativa. */
export function render(container: HTMLElement, dados: readonly Kpi[], opcoes: OpcoesKpi = {}): Grafico<readonly Kpi[]> {
  function atualizar(novos: readonly Kpi[]): void {
    const lista = document.createElement("dl");
    lista.className = "kpis";
    for (const k of novos) {
      const cartao = document.createElement("div");
      cartao.className = "kpi";
      const dt = document.createElement("dt");
      if (k.ajuda !== undefined && opcoes.ajuda) {
        // A última palavra e o "?" formam um bloco que não se separa: o "?" nunca fica sozinho na linha de baixo.
        const corte = k.rotulo.lastIndexOf(" ") + 1;
        const fim = document.createElement("span");
        fim.className = "kpi-fim";
        fim.append(k.rotulo.slice(corte), " ", opcoes.ajuda(k.ajuda));
        dt.append(k.rotulo.slice(0, corte), fim);
      } else dt.textContent = k.rotulo;
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
      if (k.fonte !== undefined && opcoes.fonte) {
        // Linha própria: ao lado do título o chip quebrava de linha em cartões estreitos.
        const f = document.createElement("dd");
        f.className = "fonte-linha";
        f.append(opcoes.fonte(k.fonte));
        cartao.append(f);
      }
      lista.append(cartao);
    }
    container.replaceChildren(lista);
  }
  atualizar(dados);
  return { atualizar, destruir: () => { container.replaceChildren(); } };
}
