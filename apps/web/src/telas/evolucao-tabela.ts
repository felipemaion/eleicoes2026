/** Tabela comparativa 2022 × 2026 por pessoa, ordenável por qualquer coluna (botões no cabeçalho, aria-sort). */
import { ordenarLinhas, type ColunaOrdenavel, type LinhaComparativa, type Sentido } from "../dados/evolucao-logica";
import { formatarDecimal, formatarNumero, formatarPermil } from "../formato";
import { h } from "./dom";

interface Coluna {
  chave: ColunaOrdenavel;
  rotulo: string;
  texto: boolean;
  celula: (l: LinhaComparativa) => string;
}

const sinal = (v: number | null, f: (n: number) => string): string => (v === null ? "—" : `${v > 0 ? "+" : ""}${f(v)}`);
const permil = (v: number | null): string => (v === null ? "—" : formatarPermil(v));

const COLUNAS: readonly Coluna[] = [
  { chave: "nome", rotulo: "Candidato", texto: true, celula: (l) => l.nome },
  { chave: "uf_para", rotulo: "UF", texto: true, celula: (l) => l.uf_para },
  { chave: "cargo_de", rotulo: "Cargo 2022", texto: true, celula: (l) => l.cargo_de.toLowerCase() },
  { chave: "partido_de", rotulo: "Partido 2022", texto: true, celula: (l) => l.partido_de },
  { chave: "votos_de", rotulo: "Votos 2022", texto: false, celula: (l) => formatarNumero(l.votos_de) },
  { chave: "penetracao_de", rotulo: "Penetração 2022", texto: false, celula: (l) => permil(l.penetracao_de) },
  { chave: "cargo_para", rotulo: "Cargo 2026", texto: true, celula: (l) => l.cargo_para.toLowerCase() },
  { chave: "partido_para", rotulo: "Partido 2026", texto: true, celula: (l) => l.partido_para },
  { chave: "votos_para", rotulo: "Votos 2026", texto: false, celula: (l) => formatarNumero(l.votos_para) },
  { chave: "penetracao_para", rotulo: "Penetração 2026", texto: false, celula: (l) => permil(l.penetracao_para) },
  { chave: "delta_votos", rotulo: "Δ votos", texto: false, celula: (l) => sinal(l.delta_votos, formatarNumero) },
  { chave: "delta_penetracao", rotulo: "Δ penetração", texto: false, celula: (l) => sinal(l.delta_penetracao, (n) => `${formatarDecimal(n)} ‰`) },
];

export interface TabelaPessoas {
  elemento: HTMLElement;
  atualizar(linhas: readonly LinhaComparativa[]): void;
}

export function criarTabelaPessoas(linhasIniciais: readonly LinhaComparativa[]): TabelaPessoas {
  let linhas = linhasIniciais;
  let ordem: { coluna: ColunaOrdenavel; sentido: Sentido } = { coluna: "nome", sentido: "asc" };
  const tabela = h("table", { className: "tabela-pessoas" });
  tabela.createCaption().textContent = "Candidatos escolhidos: 2022 × 2026 (clique no título da coluna para ordenar)";
  const cabecalho = tabela.createTHead().insertRow();
  const corpo = tabela.createTBody();
  const ths = new Map<ColunaOrdenavel, HTMLTableCellElement>();
  for (const c of COLUNAS) {
    const th = document.createElement("th");
    th.scope = "col";
    const b = h("button", { type: "button", textContent: c.rotulo });
    b.dataset["coluna"] = c.chave;
    b.addEventListener("click", () => {
      ordem = { coluna: c.chave, sentido: ordem.coluna === c.chave ? (ordem.sentido === "asc" ? "desc" : "asc") : c.texto ? "asc" : "desc" };
      desenhar();
      // O cabeçalho não é refeito, então o foco do botão clicado se mantém.
    });
    th.append(b);
    ths.set(c.chave, th);
    cabecalho.append(th);
  }
  function desenhar(): void {
    for (const [chave, th] of ths) {
      if (chave === ordem.coluna) th.setAttribute("aria-sort", ordem.sentido === "asc" ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    }
    corpo.replaceChildren(...ordenarLinhas(linhas, ordem.coluna, ordem.sentido).map((l) => {
      const tr = document.createElement("tr");
      COLUNAS.forEach((c, i) => {
        const cel = document.createElement(i === 0 ? "th" : "td");
        if (i === 0) (cel as HTMLTableCellElement).scope = "row";
        else if (!c.texto) cel.className = "numero";
        cel.textContent = c.celula(l);
        tr.append(cel);
      });
      return tr;
    }));
  }
  desenhar();
  // O wrapper rola na horizontal em telas estreitas; a tabela em si mantém as colunas legíveis.
  const elemento = h("div", { className: "tabela-rolavel" }, tabela);
  elemento.tabIndex = 0;
  elemento.setAttribute("role", "region");
  elemento.setAttribute("aria-label", "Tabela comparativa 2022 × 2026");
  return { elemento, atualizar(n) { linhas = n; desenhar(); } };
}
