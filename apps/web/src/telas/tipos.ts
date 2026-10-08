import type { Estado } from "../store";

/** Contrato de toda tela: desenha dentro do contêiner recebido. */
export interface Tela {
  titulo: string;
  render(container: HTMLElement, estado: Readonly<Estado>): void;
}

export function placeholder(titulo: string, descricao: string): Tela {
  return {
    titulo,
    render(container, { filtros }) {
      const h1 = document.createElement("h1");
      h1.textContent = titulo;
      h1.tabIndex = -1;
      const bloco = document.createElement("div");
      bloco.className = "conteudo-reservado";
      bloco.textContent = `${descricao} Filtros: UF ${filtros.uf} · cargo ${filtros.cargo} · grupo ${filtros.grupo} · ${String(filtros.ano)}.`;
      container.replaceChildren(h1, bloco);
    },
  };
}
