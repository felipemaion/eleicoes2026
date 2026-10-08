/** Formatação pt-BR compartilhada (um só lugar para separadores e casas decimais). */
const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const percentual = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const formatarInteiro = (v: number): string => inteiro.format(v);
export const formatarDecimal = (v: number): string => decimal.format(v);
/** Recebe fração (0,0456) e devolve "4,6%". */
export const formatarPercentual = (v: number): string => percentual.format(v);
