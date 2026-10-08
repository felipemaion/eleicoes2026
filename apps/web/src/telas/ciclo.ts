import type { Estado, Tela as Chave } from "../store";
import type { Tela } from "./tipos";

export interface GerenciadorDeTelas {
  desenhar(estado: Readonly<Estado>): void;
  destruir(): void;
}

/** Garante que o `dispose` da renderização anterior rode antes de cada novo render. */
export function criarGerenciadorDeTelas(container: HTMLElement, telas: Readonly<Record<Chave, Tela>>): GerenciadorDeTelas {
  let dispose: (() => void) | null = null;
  const liberar = (): void => {
    const d = dispose;
    dispose = null;
    d?.();
  };
  return {
    desenhar(estado) {
      liberar();
      dispose = telas[estado.tela].render(container, estado);
    },
    destruir: liberar,
  };
}
