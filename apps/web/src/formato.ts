/** Formatação pt-BR compartilhada (um só lugar para separadores e casas decimais). */
const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const percentual = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const formatarInteiro = (v: number): string => inteiro.format(v);
export const formatarDecimal = (v: number): string => decimal.format(v);
/** Recebe fração (0,0456) e devolve "4,6%". */
export const formatarPercentual = (v: number): string => percentual.format(v);

import { formatLocale } from "d3";

/** Locale D3 pt-BR: vírgula decimal, ponto de milhar, R$ — usado nos eixos e rótulos dos gráficos. */
export const localePtBR = formatLocale({
  decimal: ",",
  thousands: ".",
  grouping: [3],
  currency: ["R$ ", ""],
});

const fMoeda = localePtBR.format("$,.2f");
const fNumero = localePtBR.format(",.0f");

/** 1234.56 → "R$ 1.234,56". */
export const formatarMoeda = (v: number): string => fMoeda(v);
/** 1234567 → "1.234.567". */
export const formatarNumero = (v: number): string => fNumero(v);
