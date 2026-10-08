/** Tabela das candidaturas escolhidas nos lados (alternativa em texto aos mapas e KPIs). */
import type { Ficha } from "../dados/contrato";
import { formatarNumero, formatarPermil } from "../formato";
import { h } from "./dom";
import { TEXTOS_COMPARADOR as T } from "../textos";

export type CandidaturaFicha = Ficha["candidato"];

const COLUNAS = ["Ano", "Candidato", "Partido", "UF", "Votos", "Penetração"] as const;

/** `null` quando nenhum lado tem candidatos escolhidos (só grupos): não há o que listar. */
export function tabelaCandidaturas(linhas: readonly CandidaturaFicha[]): HTMLElement | null {
  if (linhas.length === 0) return null;
  const tabela = h("table", { className: "tabela-pessoas" });
  tabela.createCaption().textContent = "Votos e penetração de cada candidatura escolhida, por ano";
  const cab = tabela.createTHead().insertRow();
  for (const c of COLUNAS) cab.append(h("th", { scope: "col", textContent: c }));
  const corpo = tabela.createTBody();
  for (const l of linhas) {
    const tr = corpo.insertRow();
    const celula = (t: string, numero = false): HTMLTableCellElement => h("td", { textContent: t, className: numero ? "numero" : "" });
    tr.append(celula(String(l.ano)), h("th", { scope: "row", textContent: l.nm_urna }), celula(l.partido.sigla), celula(l.sg_uf), celula(formatarNumero(l.votos), true), celula(l.penetracao === null ? "—" : formatarPermil(l.penetracao), true));
  }
  return h("section", { className: "evolucao-tabela" }, h("h2", { textContent: T.tabelaTitulo }), h("div", { className: "tabela-rolagem" }, tabela));
}
