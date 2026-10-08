/** Painel lateral do município: resumo por grupo e cargo (`/municipios/{ibge}`), em tabela. */
import type { RespostaMunicipio } from "../dados/contrato";
import { formatarDecimal, formatarInteiro } from "../formato";
import { h } from "./dom";

// A unidade (‰, %) vai no cabeçalho: repetida em cada célula, ela só alarga a coluna.
const semDado = (v: number | null): string => (v === null ? "sem dado" : formatarDecimal(v));

/** Cabeçalhos curtos (não quebram no meio); o nome completo fica no `title`. */
const COLUNAS: readonly { curto: string; completo: string; numerica: boolean }[] = [
  { curto: "Cargo", completo: "Cargo disputado", numerica: false },
  { curto: "Cand.", completo: "Candidaturas do grupo", numerica: true },
  { curto: "Votos", completo: "Votos nominais", numerica: true },
  { curto: "Aptos", completo: "Eleitores aptos", numerica: true },
  { curto: "Penetr. (‰)", completo: "Penetração: votos por mil eleitores aptos (‰)", numerica: true },
  { curto: "% válidos", completo: "Percentual dos votos válidos do cargo", numerica: true },
];
const cargoLegivel = (c: string): string => c.charAt(0) + c.slice(1).toLowerCase();

export function desenharMunicipio(destino: HTMLElement, m: RespostaMunicipio): void {
  const titulo = h("h2", { textContent: `${m.nome} (${m.uf})`, tabIndex: -1 });
  const secoes = m.grupos.map((g) => h("section", {},
    h("h3", { textContent: `${g.rotulo} · ${String(g.ano)}` }),
    h("div", { className: "tabela-rolavel" }, h("table", { className: "tabela-painel" },
      h("caption", { textContent: `Votos de ${g.rotulo} em ${m.nome}` }),
      h("thead", {}, h("tr", {}, ...COLUNAS.map((c) => h("th", { textContent: c.curto, title: c.completo, scope: "col", className: c.numerica ? "numero" : "" })))),
      h("tbody", {}, ...g.cargos.map((c) => h("tr", {},
        h("th", { textContent: cargoLegivel(c.cargo), scope: "row" }),
        h("td", { textContent: formatarInteiro(c.n_candidaturas), className: "numero" }),
        h("td", { textContent: formatarInteiro(c.votos), className: "numero" }),
        h("td", { textContent: formatarInteiro(c.aptos), className: "numero" }),
        h("td", { textContent: semDado(c.penetracao), className: "numero" }),
        h("td", { textContent: semDado(c.pct_validos), className: "numero" }),
      ))),
    )),
  ));
  destino.replaceChildren(titulo, ...secoes, h("p", { className: "nota", textContent: "Penetração: votos por mil eleitores aptos do cargo no município (‰)." }));
}

/** Leva o foco ao título do painel: quem escolheu pelo teclado ouve o município anunciado. */
export function focarPainel(destino: HTMLElement): void {
  destino.querySelector<HTMLElement>("h2")?.focus();
}
