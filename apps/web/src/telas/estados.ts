/** Estados de carregando / erro / vazio, iguais em todas as telas. */
import { h } from "./dom";

export function mostrarCarregando(destino: HTMLElement): void {
  destino.replaceChildren(h("p", { className: "estado", textContent: "Carregando…" }));
  destino.firstElementChild?.setAttribute("role", "status");
}

export function mostrarErro(destino: HTMLElement, erro: unknown, tentarDeNovo: () => void): void {
  const msg = erro instanceof Error ? erro.message : String(erro);
  const aviso = h("div", { className: "estado erro" }, h("p", { textContent: `Não foi possível carregar os dados. ${msg}` }));
  aviso.setAttribute("role", "alert");
  const botao = h("button", { type: "button", textContent: "Tentar novamente" });
  botao.addEventListener("click", tentarDeNovo);
  aviso.append(botao);
  destino.replaceChildren(aviso);
}

export function mostrarVazio(destino: HTMLElement, mensagem: string): void {
  destino.replaceChildren(h("p", { className: "estado vazio", textContent: mensagem }));
}

/**
 * Busca → desenha, com estados. `vazio` devolve a mensagem quando não há dado (ou null).
 * `desenhar` pode devolver um dispose. O retorno cancela resposta tardia e libera o desenho.
 */
export function carregar<T>(
  destino: HTMLElement,
  buscar: () => Promise<T>,
  vazio: (dados: T) => string | null,
  desenhar: (dados: T, destino: HTMLElement) => (() => void) | undefined,
): () => void {
  let ativo = true;
  let dispose: (() => void) | undefined;
  const executar = (): void => {
    dispose?.();
    dispose = undefined;
    mostrarCarregando(destino);
    buscar().then(
      (dados) => {
        if (!ativo) return;
        const msg = vazio(dados);
        if (msg !== null) { mostrarVazio(destino, msg); return; }
        destino.replaceChildren();
        dispose = desenhar(dados, destino);
      },
      (erro: unknown) => { if (ativo) mostrarErro(destino, erro, executar); },
    );
  };
  executar();
  return () => {
    ativo = false;
    dispose?.();
    dispose = undefined;
    destino.replaceChildren();
  };
}
