import { renderizarMarkdown } from "../markdown";
import { h, titulo } from "./dom";
import { carregar } from "./estados";
import type { Tela } from "./tipos";

/** "Como ler este painel": o README público escrito pelo analista, copiado no build (import `?raw`). */
export const tela: Tela = {
  titulo: "Como ler este painel",
  render(container) {
    const conteudo = h("article", { className: "como-ler" });
    container.replaceChildren(titulo("Como ler este painel"), conteudo);
    // Import dinâmico: o texto só é baixado por quem abre a página.
    const parar = carregar(
      conteudo,
      () => import("../../../../docs/metodologia/publico/README.md?raw").then((m) => m.default),
      () => null,
      (md, destino) => { destino.append(renderizarMarkdown(md)); return undefined; },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
