/** Divisória arrastável entre dois quadros lado a lado (mapa × painel). A lógica de limites é pura. */

export const PASSO_TECLADO = 24;
export const PASSO_TECLADO_GRANDE = 96;

/** Mantém a largura do painel entre `min` e `max`; se os limites se cruzarem (tela apertada), vale `min`. */
export function limitarLargura(valor: number, min: number, max: number): number {
  const teto = Math.max(min, max);
  return Math.round(Math.min(Math.max(valor, min), teto));
}

/**
 * Nova largura do painel para uma tecla, ou `null` se a tecla não é da divisória.
 * O painel fica à direita: seta ← aumenta o painel (a linha vai para a esquerda).
 */
export function larguraPorTecla(tecla: string, atual: number, min: number, max: number, grande = false): number | null {
  const passo = grande ? PASSO_TECLADO_GRANDE : PASSO_TECLADO;
  switch (tecla) {
    case "ArrowLeft": return limitarLargura(atual + passo, min, max);
    case "ArrowRight": return limitarLargura(atual - passo, min, max);
    case "Home": return limitarLargura(min, min, max);
    case "End": return limitarLargura(max, min, max);
    default: return null;
  }
}

export interface OpcoesDivisoria {
  /** Elemento-grade que contém [mapa, divisória, painel]; recebe `--painel-largura`. */
  layout: HTMLElement;
  /** Largura padrão do painel (px) e limites mínimos de cada lado. */
  padrao: number;
  minPainel: number;
  minMapa: number;
  /** Chave do localStorage onde a largura é guardada. */
  chave: string;
  rotulo: string;
  /** Chamado (já limitado por rAF) quando a largura muda: o mapa recalcula o tamanho. */
  aoRedimensionar?: () => void;
}

export interface Divisoria {
  elemento: HTMLElement;
  largura(): number;
  destruir(): void;
}

const LARGURA_DA_DIVISORIA = 16;

function lerGuardada(chave: string): number | null {
  try {
    const bruto = window.localStorage.getItem(chave);
    const n = bruto === null ? NaN : Number(bruto);
    return Number.isFinite(n) ? n : null;
  } catch { return null; }
}

function guardar(chave: string, valor: number | null): void {
  try {
    if (valor === null) window.localStorage.removeItem(chave);
    else window.localStorage.setItem(chave, String(valor));
  } catch { /* sem storage: a largura vale só nesta visita */ }
}

export function criarDivisoria(o: OpcoesDivisoria): Divisoria {
  const el = document.createElement("div");
  el.className = "divisoria";
  el.tabIndex = 0;
  el.setAttribute("role", "separator");
  el.setAttribute("aria-orientation", "vertical");
  el.setAttribute("aria-label", o.rotulo);
  el.title = "Arraste, ou use as setas ← →, para mudar a largura. Duplo clique restaura.";

  let largura = o.padrao;
  // O que a pessoa pediu; `largura` é o que cabe agora. Janela estreita não pode "esquecer" o pedido.
  let desejada = o.padrao;
  let quadro = 0;
  const maximo = (): number => o.layout.clientWidth - o.minMapa - LARGURA_DA_DIVISORIA;
  const avisar = (): void => {
    if (quadro !== 0) return;
    quadro = requestAnimationFrame(() => { quadro = 0; o.aoRedimensionar?.(); });
  };
  const aplicar = (v: number, persistir: boolean, pedido = true): void => {
    if (pedido) desejada = v;
    largura = limitarLargura(v, o.minPainel, maximo());
    o.layout.style.setProperty("--painel-largura", `${String(largura)}px`);
    el.setAttribute("aria-valuemin", String(o.minPainel));
    el.setAttribute("aria-valuemax", String(Math.max(o.minPainel, maximo())));
    el.setAttribute("aria-valuenow", String(largura));
    if (persistir) guardar(o.chave, largura);
    avisar();
  };

  let arrasto: { x: number; largura: number } | null = null;
  el.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    arrasto = { x: e.clientX, largura };
    el.setPointerCapture(e.pointerId);
    el.classList.add("arrastando");
    e.preventDefault();
  });
  el.addEventListener("pointermove", (e) => {
    if (arrasto) aplicar(arrasto.largura - (e.clientX - arrasto.x), false);
  });
  const soltar = (e: PointerEvent): void => {
    if (!arrasto) return;
    arrasto = null;
    el.classList.remove("arrastando");
    if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
    guardar(o.chave, largura);
  };
  el.addEventListener("pointerup", soltar);
  el.addEventListener("pointercancel", soltar);
  el.addEventListener("keydown", (e) => {
    const nova = larguraPorTecla(e.key, largura, o.minPainel, maximo(), e.shiftKey);
    if (nova === null) return;
    e.preventDefault();
    aplicar(nova, true);
  });
  el.addEventListener("dblclick", () => { guardar(o.chave, null); aplicar(o.padrao, false); });

  // O layout só tem largura depois de entrar no documento; ao mudar de tamanho (janela menor),
  // o painel encolhe para o mapa manter o mínimo. A leitura inicial também passa por aqui.
  desejada = lerGuardada(o.chave) ?? o.padrao;
  const observador = new ResizeObserver(() => { aplicar(desejada, false, false); });
  observador.observe(o.layout);
  aplicar(desejada, false);
  return {
    elemento: el,
    largura: () => largura,
    destruir() {
      observador.disconnect();
      if (quadro !== 0) cancelAnimationFrame(quadro);
    },
  };
}
