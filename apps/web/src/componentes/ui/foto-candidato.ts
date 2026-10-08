/** Foto do candidato (com placeholder) e abertura da página dele no TSE: usados por tooltips e busca. */

const CONECTIVOS = new Set(["da", "de", "do", "das", "dos", "e"]);

/** Iniciais das duas primeiras palavras significativas; "?" quando o nome é vazio. */
export function iniciais(nome: string): string {
  const palavras = nome.trim().split(/\s+/).filter((p) => p !== "" && !CONECTIVOS.has(p.toLowerCase()));
  const letras = palavras.slice(0, 2).map((p) => p.charAt(0).toUpperCase()).join("");
  return letras === "" ? "?" : letras;
}

/** Foto 80×100 (proporção do WebP 160×200 da API); tamanho fixo evita salto de layout. Sem URL, vira iniciais. Tooltip usa `eager`: um balão efêmero com img lazy pode nunca chegar a carregar. */
export function figuraCandidato(nome: string, url: string | null, largura = 80, altura = 100, carga: "lazy" | "eager" = "lazy"): HTMLElement {
  const f = document.createElement("span");
  f.className = "foto-candidato";
  f.style.width = `${String(largura)}px`;
  f.style.height = `${String(altura)}px`;
  if (url === null) {
    f.classList.add("sem-foto");
    f.setAttribute("role", "img");
    f.setAttribute("aria-label", `Sem foto de ${nome}`);
    f.textContent = iniciais(nome);
    return f;
  }
  const img = document.createElement("img");
  img.src = url;
  img.alt = `Foto de ${nome}`;
  img.setAttribute("loading", carga);
  img.setAttribute("decoding", "async");
  img.width = largura;
  img.height = altura;
  f.append(img);
  return f;
}

export interface LinkTse { url: string; verificado: boolean; nota: string | null }

/** Linhas de rodapé do tooltip: o convite ao clique e, se o padrão de URL não foi conferido, a nota da API. */
export function avisoLinkTse(l: LinkTse): string[] {
  const linhas = ["Clique para abrir no TSE (nova aba)."];
  if (!l.verificado) linhas.push(`Link não verificado: ${l.nota ?? "padrão a conferir"}`);
  return linhas;
}

/** Abre a página oficial em nova aba, sem `opener` nem `referrer`. Só https: o dado vem da API, mas não é confiável às cegas. */
export function abrirNoTse(url: string): void {
  if (!url.startsWith("https://")) return;
  window.open(url, "_blank", "noopener,noreferrer");
}
