/** Sobreposição de carregamento sobre a tela toda; só aparece se a espera passar de 200 ms. */
export interface Sobreposicao {
  raiz: HTMLElement;
  /** Registra uma carga; devolve a função que a encerra (idempotente). */
  iniciar(texto: string): () => void;
}

const ATRASO_MS = 200;
// Uma vez visível, fica um instante para não "piscar" quando a resposta chega logo depois.
const PERMANENCIA_MS = 250;

export function criarSobreposicao(pai: HTMLElement, areaOcupada?: HTMLElement): Sobreposicao {
  const raiz = document.createElement("div");
  raiz.className = "sobreposicao";
  raiz.hidden = true;
  raiz.setAttribute("role", "status");
  raiz.setAttribute("aria-live", "polite");
  const giro = document.createElement("span");
  giro.className = "sobreposicao-giro";
  giro.setAttribute("aria-hidden", "true");
  const texto = document.createElement("p");
  texto.className = "sobreposicao-texto";
  raiz.append(giro, texto);
  pai.append(raiz);

  const ativas = new Map<number, string>();
  let proximo = 0;
  let aparecer: ReturnType<typeof setTimeout> | undefined;
  let sumir: ReturnType<typeof setTimeout> | undefined;
  let visivelDesde = 0;

  const atualizar = (): void => {
    const ultimo = [...ativas.values()].at(-1);
    if (ultimo !== undefined) {
      texto.textContent = ultimo;
      clearTimeout(sumir);
      if (raiz.hidden && aparecer === undefined) {
        aparecer = setTimeout(() => {
          aparecer = undefined;
          if (ativas.size === 0) return;
          raiz.hidden = false;
          visivelDesde = Date.now();
          areaOcupada?.setAttribute("aria-busy", "true");
        }, ATRASO_MS);
      }
      return;
    }
    clearTimeout(aparecer);
    aparecer = undefined;
    if (raiz.hidden) { areaOcupada?.setAttribute("aria-busy", "false"); return; }
    clearTimeout(sumir);
    sumir = setTimeout(() => {
      raiz.hidden = true;
      areaOcupada?.setAttribute("aria-busy", "false");
    }, Math.max(0, PERMANENCIA_MS - (Date.now() - visivelDesde)));
  };

  return {
    raiz,
    iniciar(t) {
      const id = ++proximo;
      ativas.set(id, t);
      atualizar();
      return () => { if (ativas.delete(id)) atualizar(); };
    },
  };
}

let global: Sobreposicao | null = null;
/** Registrada por `main.ts`; sem ela (testes de unidade de telas) as cargas seguem sem overlay. */
export function definirSobreposicaoGlobal(s: Sobreposicao | null): void { global = s; }
export function iniciarCarga(texto: string): () => void { return global ? global.iniciar(texto) : () => { /* sem overlay */ }; }
