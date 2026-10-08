/** JSON importado alarga o enum `abrangencia.tipo` para `string`; estas funções o estreitam sem calar o resto do contrato. */
interface ComAbrangencia { abrangencia: { tipo: string; uf: string | null } }
const estreitar = <T extends ComAbrangencia>(x: T): Omit<T, "abrangencia"> & { abrangencia: { tipo: "pais" | "uf"; uf: string | null } } =>
  ({ ...x, abrangencia: { uf: x.abrangencia.uf, tipo: x.abrangencia.tipo === "pais" ? "pais" : "uf" } });

export const listaTipada = <L extends { itens: ComAbrangencia[] }>(l: L): Omit<L, "itens"> & { itens: ReturnType<typeof estreitar<L["itens"][number]>>[] } =>
  ({ ...l, itens: l.itens.map(estreitar) });
type TipoLink = "votos_oficiais" | "divulgacand_lista" | "divulgacand_candidato" | "divulgacand_ficha_json" | "dados_abertos_votos" | "dados_abertos_contas";
const TIPOS_LINK: readonly string[] = ["votos_oficiais", "divulgacand_lista", "divulgacand_candidato", "divulgacand_ficha_json", "dados_abertos_votos", "dados_abertos_contas"];
const estreitarLink = <L extends { tipo: string }>(l: L): Omit<L, "tipo"> & { tipo: TipoLink } => {
  if (!TIPOS_LINK.includes(l.tipo)) throw new Error(`fixture com tipo de link fora do contrato: ${l.tipo}`);
  return { ...l, tipo: l.tipo as TipoLink };
};
export const fichaTipada = <F extends { candidato: ComAbrangencia; links: { tipo: string }[] }>(f: F): Omit<F, "candidato" | "links"> & { candidato: ReturnType<typeof estreitar<F["candidato"]>>; links: ReturnType<typeof estreitarLink<F["links"][number]>>[] } =>
  ({ ...f, candidato: estreitar(f.candidato), links: f.links.map(estreitarLink) });

type Estreito<T extends ComAbrangencia> = ReturnType<typeof estreitar<T>>;
type ItemPessoa = { de: ComAbrangencia; para: ComAbrangencia };
type PessoaTipada<I extends ItemPessoa> = Omit<I, "de" | "para"> & { de: Estreito<I["de"]>; para: Estreito<I["para"]> };
export const pessoasTipadas = <L extends { itens: ItemPessoa[] }>(l: L): Omit<L, "itens"> & { itens: PessoaTipada<L["itens"][number]>[] } => {
  const { itens, ...resto } = l;
  return { ...resto, itens: itens.map((i) => ({ ...i, de: estreitar(i.de), para: estreitar(i.para) }) as PessoaTipada<L["itens"][number]>) };
};
