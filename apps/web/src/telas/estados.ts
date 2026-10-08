/** Estados de carregando / erro / vazio, iguais em todas as telas. */
import { iniciarCarga } from "../componentes/ui/sobreposicao";
import { h } from "./dom";

/**
 * Reserva o espaço do conteúdo (sem salto de layout). O aviso "Carregando…" fica por conta da
 * sobreposição de tela cheia, que é o `role=status` único da página.
 */
export function mostrarCarregando(destino: HTMLElement): void {
  const reserva = h("div", { className: "reserva-carga" });
  reserva.setAttribute("aria-busy", "true");
  destino.replaceChildren(reserva);
}

export function mostrarErro(destino: HTMLElement, erro: unknown, tentarDeNovo: () => void): void {
  // O detalhe técnico (URL, status) vai ao console para diagnóstico; o público lê só a mensagem amigável.
  console.error("Falha ao carregar dados:", erro);
  const aviso = h("div", { className: "estado erro" }, h("p", { textContent: "Não foi possível carregar os dados agora. Tente novamente em instantes." }));
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
  rotulo = "Carregando dados…",
): () => void {
  let ativo = true;
  let encerrarCarga: (() => void) | undefined;
  let dispose: (() => void) | undefined;
  const executar = (): void => {
    dispose?.();
    dispose = undefined;
    mostrarCarregando(destino);
    encerrarCarga?.();
    const fim = (encerrarCarga = iniciarCarga(rotulo));
    buscar().then(
      (dados) => {
        fim();
        if (!ativo) return;
        const msg = vazio(dados);
        if (msg !== null) { mostrarVazio(destino, msg); return; }
        destino.replaceChildren();
        dispose = desenhar(dados, destino);
      },
      (erro: unknown) => { fim(); if (ativo) mostrarErro(destino, erro, executar); },
    );
  };
  executar();
  return () => {
    ativo = false;
    encerrarCarga?.();
    dispose?.();
    dispose = undefined;
    destino.replaceChildren();
  };
}
