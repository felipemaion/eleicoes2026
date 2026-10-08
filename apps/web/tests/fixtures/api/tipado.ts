/** JSON importado alarga o enum `abrangencia.tipo` para `string`; estas funções o estreitam sem calar o resto do contrato. */
interface ComAbrangencia { abrangencia: { tipo: string; uf: string | null } }
const estreitar = <T extends ComAbrangencia>(x: T): Omit<T, "abrangencia"> & { abrangencia: { tipo: "pais" | "uf"; uf: string | null } } =>
  ({ ...x, abrangencia: { uf: x.abrangencia.uf, tipo: x.abrangencia.tipo === "pais" ? "pais" : "uf" } });

export const listaTipada = <L extends { itens: ComAbrangencia[] }>(l: L): Omit<L, "itens"> & { itens: ReturnType<typeof estreitar<L["itens"][number]>>[] } =>
  ({ ...l, itens: l.itens.map(estreitar) });
export const fichaTipada = <F extends { candidato: ComAbrangencia }>(f: F): Omit<F, "candidato"> & { candidato: ReturnType<typeof estreitar<F["candidato"]>> } =>
  ({ ...f, candidato: estreitar(f.candidato) });
