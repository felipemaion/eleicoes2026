/**
 * Comportamento do cabeçalho compacto (≤ 768 px): menu ☰ e busca que abre por cima da barra.
 * O CSS decide o que aparece; aqui só estado, foco e fechamento — inofensivo no desktop,
 * onde os botões ficam ocultos.
 */

export interface PartesCabecalho {
  readonly cabecalho: HTMLElement;
  readonly botaoMenu: HTMLButtonElement;
  readonly painelMenu: HTMLElement;
  readonly botaoBusca: HTMLButtonElement;
  readonly slotBusca: HTMLElement;
}

const FOCAVEIS = 'a[href], button:not([disabled]), input:not([disabled]), select, [tabindex]:not([tabindex="-1"])';

/** Próximo índice de foco dentro de um ciclo (Tab / Shift+Tab); -1 = foco ainda fora da lista. */
export function proximoIndiceDeFoco(atual: number, total: number, voltar: boolean): number {
  if (total <= 0) return -1;
  if (atual < 0) return voltar ? total - 1 : 0;
  return (atual + (voltar ? -1 : 1) + total) % total;
}

const visivel = (e: HTMLElement): boolean => e.getClientRects().length > 0;

export function ligarCabecalhoMovel(p: PartesCabecalho): () => void {
  const { cabecalho, botaoMenu, painelMenu, botaoBusca, slotBusca } = p;
  const mq = window.matchMedia("(max-width: 768px)");

  const definir = (botao: HTMLButtonElement, atributo: string, aberto: boolean): void => {
    cabecalho.toggleAttribute(atributo, aberto);
    botao.setAttribute("aria-expanded", String(aberto));
  };
  const menuAberto = (): boolean => cabecalho.hasAttribute("data-menu-aberto");
  const buscaAberta = (): boolean => cabecalho.hasAttribute("data-busca-aberta");

  const fecharMenu = (devolverFoco: boolean): void => {
    if (!menuAberto()) return;
    definir(botaoMenu, "data-menu-aberto", false);
    if (devolverFoco) botaoMenu.focus();
  };
  const fecharBusca = (devolverFoco: boolean): void => {
    if (!buscaAberta()) return;
    definir(botaoBusca, "data-busca-aberta", false);
    if (devolverFoco) botaoBusca.focus();
  };

  botaoMenu.addEventListener("click", () => {
    if (menuAberto()) { fecharMenu(true); return; }
    fecharBusca(false);
    definir(botaoMenu, "data-menu-aberto", true);
    painelMenu.querySelector<HTMLElement>("a[href]")?.focus();
  });
  botaoBusca.addEventListener("click", () => {
    if (buscaAberta()) { fecharBusca(true); return; }
    fecharMenu(false);
    definir(botaoBusca, "data-busca-aberta", true);
    slotBusca.querySelector<HTMLInputElement>("input")?.focus();
  });

  // Capture: precisa ver o estado da lista de sugestões antes de o combobox tratar o mesmo Esc.
  cabecalho.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      const alvo = ev.target instanceof HTMLElement ? ev.target : null;
      if (alvo?.getAttribute("aria-expanded") === "true" && alvo !== botaoMenu && alvo !== botaoBusca) return;
      if (menuAberto()) { ev.preventDefault(); fecharMenu(true); }
      else if (buscaAberta()) { ev.preventDefault(); fecharBusca(true); }
      return;
    }
    if (ev.key !== "Tab" || !menuAberto()) return;
    const itens = [botaoMenu, ...Array.from(painelMenu.querySelectorAll<HTMLElement>(FOCAVEIS)).filter(visivel)];
    const i = proximoIndiceDeFoco(itens.indexOf(document.activeElement as HTMLElement), itens.length, ev.shiftKey);
    if (i >= 0) { ev.preventDefault(); itens[i]?.focus(); }
  }, true);

  painelMenu.addEventListener("click", (ev) => {
    if ((ev.target as HTMLElement).closest("a[href]")) fecharMenu(false);
  });
  document.addEventListener("pointerdown", (ev) => {
    if (ev.target instanceof Node && !cabecalho.contains(ev.target)) { fecharMenu(false); fecharBusca(false); }
  });
  window.addEventListener("hashchange", () => { fecharMenu(false); fecharBusca(false); });
  mq.addEventListener("change", () => { fecharMenu(false); fecharBusca(false); });
  return () => { fecharMenu(false); fecharBusca(false); };
}
