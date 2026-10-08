/** O jsdom não traz ResizeObserver (os navegadores sim): stub inerte para as telas que o usam. */
class ResizeObserverInerte implements ResizeObserver {
  observe(): void { /* sem layout no jsdom */ }
  unobserve(): void { /* idem */ }
  disconnect(): void { /* idem */ }
}
// O tipo do DOM diz que sempre existe; no jsdom não existe — daí o `in`.
if (!("ResizeObserver" in globalThis)) globalThis.ResizeObserver = ResizeObserverInerte;
