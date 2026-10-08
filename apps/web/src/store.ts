/** Estado global mínimo e tipado: tela atual + filtros compartilhados. */

export const TELAS = ["visao-geral", "mapa", "gastos", "evolucao", "candidato", "como-ler"] as const;
export type Tela = (typeof TELAS)[number];

export const UFS = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
  "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
] as const;
export type Uf = (typeof UFS)[number] | "BR";

/** Sem "todos": somar cargos diferentes (presidente + deputados) daria um número sem significado. */
export const CARGOS = ["deputado_federal", "deputado_estadual", "senador", "governador", "presidente"] as const;
export type Cargo = (typeof CARGOS)[number];

/** Id de grupo de `config/grupos.yaml`; a lista válida vem da API (`/api/grupos`), não do código. */
export type Grupo = string;

export const ANOS = [2022, 2026] as const;
export type Ano = (typeof ANOS)[number];

export interface Filtros {
  uf: Uf;
  cargo: Cargo;
  grupo: Grupo;
  ano: Ano;
  /** Candidato da tela "Candidato", no formato `ano:sq_candidato`; vazio = nenhum. */
  candidato: string;
  /** Seleção da Evolução: `pessoa_id_publico` separados por vírgula; vazio = grupo inteiro. */
  pessoas: string;
}

export const FILTROS_PADRAO: Readonly<Filtros> = { uf: "BR", cargo: "deputado_federal", grupo: "missao_2026", ano: 2026, candidato: "", pessoas: "" };

import { normalizarFiltros } from "./filtros-logica";

export interface Estado {
  tela: Tela;
  filtros: Filtros;
}

/** `ajuste` = o filtro foi corrigido para refletir o candidato aberto; a tela não precisa se redesenhar. */
export type Ouvinte = (estado: Readonly<Estado>, ajuste?: boolean) => void;

export interface Store {
  obter(): Readonly<Estado>;
  /** Aplica mudança parcial; não notifica se nada mudou. */
  definir(filtros: Partial<Filtros>, tela?: Tela): void;
  /** Como `definir`, mas avisa com `ajuste=true`: usado para o recorte seguir o candidato sem refazer a tela. */
  ajustar(filtros: Partial<Filtros>): void;
  assinar(ouvinte: Ouvinte): () => void;
}

export function criarStore(inicial: Estado = { tela: "visao-geral", filtros: { ...FILTROS_PADRAO } }): Store {
  let estado: Estado = inicial;
  const ouvintes = new Set<Ouvinte>();
  function aplicar(filtros: Partial<Filtros>, tela: Tela | undefined, ajuste: boolean): void {
    const proximo: Estado = { tela: tela ?? estado.tela, filtros: normalizarFiltros({ ...estado.filtros, ...filtros }) };
    const igual =
      proximo.tela === estado.tela &&
      (Object.keys(proximo.filtros) as (keyof Filtros)[]).every((k) => proximo.filtros[k] === estado.filtros[k]);
    if (igual) return;
    estado = proximo;
    ouvintes.forEach((o) => { o(estado, ajuste); });
  }
  return {
    obter: () => estado,
    definir: (filtros, tela) => { aplicar(filtros, tela, false); },
    ajustar: (filtros) => { aplicar(filtros, undefined, true); },
    assinar(ouvinte) {
      ouvintes.add(ouvinte);
      return () => ouvintes.delete(ouvinte);
    },
  };
}
