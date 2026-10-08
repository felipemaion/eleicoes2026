/** Estado global mínimo e tipado: tela atual + filtros compartilhados. */

export const TELAS = ["visao-geral", "mapa", "gastos", "evolucao", "candidato"] as const;
export type Tela = (typeof TELAS)[number];

export const UFS = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
  "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
] as const;
export type Uf = (typeof UFS)[number] | "BR";

export const CARGOS = ["todos", "deputado_federal", "deputado_estadual", "senador", "governador", "presidente"] as const;
export type Cargo = (typeof CARGOS)[number];

export const GRUPOS = ["missao_2026", "mbl_2022"] as const;
export type Grupo = (typeof GRUPOS)[number];

export const ANOS = [2022, 2026] as const;
export type Ano = (typeof ANOS)[number];

export interface Filtros {
  uf: Uf;
  cargo: Cargo;
  grupo: Grupo;
  ano: Ano;
}

export const FILTROS_PADRAO: Readonly<Filtros> = { uf: "BR", cargo: "todos", grupo: "missao_2026", ano: 2026 };

export interface Estado {
  tela: Tela;
  filtros: Filtros;
}

export type Ouvinte = (estado: Readonly<Estado>) => void;

export interface Store {
  obter(): Readonly<Estado>;
  /** Aplica mudança parcial; não notifica se nada mudou. */
  definir(filtros: Partial<Filtros>, tela?: Tela): void;
  assinar(ouvinte: Ouvinte): () => void;
}

export function criarStore(inicial: Estado = { tela: "visao-geral", filtros: { ...FILTROS_PADRAO } }): Store {
  let estado: Estado = inicial;
  const ouvintes = new Set<Ouvinte>();
  return {
    obter: () => estado,
    definir(filtros, tela) {
      const proximo: Estado = { tela: tela ?? estado.tela, filtros: { ...estado.filtros, ...filtros } };
      const igual =
        proximo.tela === estado.tela &&
        (Object.keys(proximo.filtros) as (keyof Filtros)[]).every((k) => proximo.filtros[k] === estado.filtros[k]);
      if (igual) return;
      estado = proximo;
      ouvintes.forEach((o) => { o(estado); });
    },
    assinar(ouvinte) {
      ouvintes.add(ouvinte);
      return () => ouvintes.delete(ouvinte);
    },
  };
}
