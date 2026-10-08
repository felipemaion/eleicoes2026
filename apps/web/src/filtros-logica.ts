/** Regras puras dos filtros (sem DOM): dependências entre campos, rótulos e textos de contagem. */
import { UFS, type Cargo, type Filtros, type Uf } from "./store";

export const ROTULO_CARGO: Readonly<Record<Cargo, string>> = {
  deputado_federal: "Deputado federal",
  deputado_estadual: "Deputado estadual",
  senador: "Senador",
  governador: "Governador",
  presidente: "Presidente",
};

/** Cargos cuja disputa é no país inteiro: não há recorte por UF. */
const CARGOS_NACIONAIS: readonly Cargo[] = ["presidente"];

/** Presidente é eleição nacional: a UF vira Brasil, em vez de pedir um recorte que não existe. */
export function normalizarFiltros(f: Filtros): Filtros {
  return CARGOS_NACIONAIS.includes(f.cargo) && f.uf !== "BR" ? { ...f, uf: "BR" } : f;
}

export const cargoNacional = (c: Cargo): boolean => CARGOS_NACIONAIS.includes(c);

export function contagemTexto(n: number): string {
  if (n === 0) return "Nenhuma candidatura com estes filtros — tente outro cargo, UF ou ano.";
  return `${new Intl.NumberFormat("pt-BR").format(n)} ${n === 1 ? "candidatura" : "candidaturas"}`;
}

const GRUPOS_RESUMO: Readonly<Record<string, string>> = {
  missao_2026: "Candidaturas do Partido Missão (nº 14) em 2026.",
  mbl_2022: "Candidatos ligados ao MBL em 2022, em outros partidos.",
};

export const resumoDeGrupo = (id: string): string => GRUPOS_RESUMO[id] ?? "";

const NOME_UF: Readonly<Record<string, string>> = {
  AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás",
  MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais", PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco",
  PI: "Piauí", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sul", RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina",
  SP: "São Paulo", SE: "Sergipe", TO: "Tocantins",
};

export interface OpcaoUf { valor: Uf; texto: string }

export const rotuloDaUf = (uf: Uf): string => (uf === "BR" ? "Brasil" : `${NOME_UF[uf] ?? uf} (${uf})`);

const semAcento = (s: string): string => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Opções do seletor de UF (limitadas às `disponiveis`, se dadas) filtradas pelo que se digitou (nome sem acento ou sigla); sigla exata primeiro. */
export function opcoesDeUf(consulta: string, disponiveis?: ReadonlySet<string>): OpcaoUf[] {
  const q = semAcento(consulta.trim());
  // Brasil sempre existe (é o recorte agregado); as demais só se o recorte tiver candidatura nelas.
  const todas: OpcaoUf[] = [{ valor: "BR", texto: "Brasil" }, ...UFS.filter((u) => disponiveis === undefined || disponiveis.has(u)).map((u) => ({ valor: u, texto: rotuloDaUf(u) }))];
  if (q === "") return todas;
  const acha = todas.filter((o) => semAcento(o.texto).includes(q) || o.valor.toLowerCase() === q);
  return [...acha.filter((o) => o.valor.toLowerCase() === q), ...acha.filter((o) => o.valor.toLowerCase() !== q)];
}
