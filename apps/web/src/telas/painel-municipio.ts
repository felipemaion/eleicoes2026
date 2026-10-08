/** Painel lateral do município: resumo por grupo e cargo (`/municipios/{ibge}`), em tabela. */
import type { RespostaMunicipio } from "../dados/contrato";
import { formatarInteiro, formatarPermil, formatarPontos } from "../formato";
import { h } from "./dom";

const semDado = (v: number | null, f: (x: number) => string): string => (v === null ? "sem dado" : f(v));
const cargoLegivel = (c: string): string => c.charAt(0) + c.slice(1).toLowerCase();

export function desenharMunicipio(destino: HTMLElement, m: RespostaMunicipio): void {
  const titulo = h("h2", { textContent: `${m.nome} (${m.uf})`, tabIndex: -1 });
  const secoes = m.grupos.map((g) => h("section", {},
    h("h3", { textContent: `${g.rotulo} · ${String(g.ano)}` }),
    h("table", {},
      h("caption", { textContent: `Votos de ${g.rotulo} em ${m.nome}` }),
      h("thead", {}, h("tr", {}, ...["Cargo", "Candidaturas", "Votos", "Aptos", "Penetração", "% válidos"].map((t) => h("th", { textContent: t, scope: "col" })))),
      h("tbody", {}, ...g.cargos.map((c) => h("tr", {},
        h("th", { textContent: cargoLegivel(c.cargo), scope: "row" }),
        h("td", { textContent: formatarInteiro(c.n_candidaturas) }),
        h("td", { textContent: formatarInteiro(c.votos) }),
        h("td", { textContent: formatarInteiro(c.aptos) }),
        h("td", { textContent: semDado(c.penetracao, formatarPermil) }),
        h("td", { textContent: semDado(c.pct_validos, formatarPontos) }),
      ))),
    ),
  ));
  destino.replaceChildren(titulo, ...secoes, h("p", { className: "nota", textContent: "Penetração: votos por mil eleitores aptos do cargo no município (‰)." }));
}

/** Leva o foco ao título do painel: quem escolheu pelo teclado ouve o município anunciado. */
export function focarPainel(destino: HTMLElement): void {
  destino.querySelector<HTMLElement>("h2")?.focus();
}
