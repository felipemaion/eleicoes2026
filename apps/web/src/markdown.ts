/**
 * Markdown mínimo e seguro para a página "Como ler este painel": títulos, parágrafos, listas,
 * tabelas, **negrito**, *itálico*, `código` e links externos. Constrói nós de DOM (nunca
 * `innerHTML`): o texto vem do repositório, mas o hábito de não injetar HTML fica.
 */

/** Marcação inline → nós. Links relativos (apontam para arquivos do repositório) ficam só como texto. */
function inline(texto: string): Node[] {
  const nos: Node[] = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[([^\]]+)\]\(([^)]+)\)/g;
  let ultimo = 0;
  for (const m of texto.matchAll(re)) {
    if (m.index > ultimo) nos.push(document.createTextNode(texto.slice(ultimo, m.index)));
    if (m[1] !== undefined) { const e = document.createElement("strong"); e.append(...inline(m[1])); nos.push(e); }
    else if (m[2] !== undefined) { const e = document.createElement("em"); e.append(...inline(m[2])); nos.push(e); }
    else if (m[3] !== undefined) { const e = document.createElement("code"); e.textContent = m[3]; nos.push(e); }
    else if (m[4] !== undefined && m[5] !== undefined) {
      if (/^https?:\/\//.test(m[5])) {
        const a = document.createElement("a");
        a.href = m[5];
        a.rel = "noopener noreferrer";
        a.textContent = m[4];
        nos.push(a);
      } else nos.push(document.createTextNode(m[4]));
    }
    ultimo = m.index + m[0].length;
  }
  if (ultimo < texto.length) nos.push(document.createTextNode(texto.slice(ultimo)));
  return nos;
}

const celulas = (linha: string): string[] => linha.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
const ehSeparadorTabela = (l: string): boolean => /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/.test(l.trim());

function el<K extends keyof HTMLElementTagNameMap>(tag: K, ...filhos: Node[]): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  e.append(...filhos);
  return e;
}

export function renderizarMarkdown(md: string): DocumentFragment {
  const saida = document.createDocumentFragment();
  const linhas = md.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  while (i < linhas.length) {
    const l = linhas[i] ?? "";
    if (l.trim() === "") { i += 1; continue; }

    const titulo = /^(#{1,4})\s+(.*)$/.exec(l);
    if (titulo) {
      // O h1 da página é da tela; o título do documento entra como h2 e os demais descem um nível.
      saida.append(el(`h${String((titulo[1] ?? "#").length + 1)}` as "h2", ...inline(titulo[2] ?? "")));
      i += 1;
      continue;
    }

    if (l.trimStart().startsWith("|") && ehSeparadorTabela(linhas[i + 1] ?? "")) {
      const cab = el("tr", ...celulas(l).map((c) => { const th = el("th", ...inline(c)); th.scope = "col"; return th; }));
      i += 2;
      const corpo: HTMLTableRowElement[] = [];
      while (i < linhas.length && (linhas[i] ?? "").trimStart().startsWith("|")) {
        corpo.push(el("tr", ...celulas(linhas[i] ?? "").map((c) => el("td", ...inline(c)))));
        i += 1;
      }
      saida.append(el("table", el("thead", cab), el("tbody", ...corpo)));
      continue;
    }

    if (/^\s*[-*]\s+/.test(l)) {
      const itens: HTMLLIElement[] = [];
      while (i < linhas.length && /^\s*[-*]\s+/.test(linhas[i] ?? "")) {
        let texto = (linhas[i] ?? "").replace(/^\s*[-*]\s+/, "");
        i += 1;
        // Linhas recuadas continuam o item anterior.
        while (i < linhas.length && /^\s{2,}\S/.test(linhas[i] ?? "") && !/^\s*[-*]\s+/.test(linhas[i] ?? "")) {
          texto += ` ${(linhas[i] ?? "").trim()}`;
          i += 1;
        }
        itens.push(el("li", ...inline(texto)));
      }
      saida.append(el("ul", ...itens));
      continue;
    }

    let texto = l.trim();
    i += 1;
    while (i < linhas.length && (linhas[i] ?? "").trim() !== "" && !/^(#{1,4}\s|\s*[-*]\s+|\|)/.test(linhas[i] ?? "")) {
      texto += ` ${(linhas[i] ?? "").trim()}`;
      i += 1;
    }
    saida.append(el("p", ...inline(texto)));
  }
  return saida;
}
