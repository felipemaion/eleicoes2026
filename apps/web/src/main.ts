import "./tokens.css";
import "./estilo.css";
import { render as renderFiltros } from "./componentes/filtros/filtros";
import { criarCliente } from "./dados/cliente";
import { cssDasCores } from "./paletas";
import { ligarStoreAoHash, ROTULOS_TELA } from "./rotas";
import { criarStore, TELAS, type Estado } from "./store";
import { TELAS_POR_CHAVE } from "./telas";
import { criarGerenciadorDeTelas } from "./telas/ciclo";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, props: Partial<HTMLElementTagNameMap[K]> = {}): HTMLElementTagNameMap[K] {
  return Object.assign(document.createElement(tag), props);
}

function montar(raiz: HTMLElement): void {
  const estilo = el("style");
  estilo.textContent = cssDasCores();
  document.head.append(estilo);

  const store = criarStore();
  const cabecalho = el("header");
  const titulo = el("h2", { textContent: "Eleições 2026 · Partido Missão (14)" });
  const nav = el("nav");
  nav.setAttribute("aria-label", "Telas");
  const lista = el("ul");
  const links = TELAS.map((chave) => {
    const a = el("a", { textContent: ROTULOS_TELA[chave] });
    const item = el("li");
    item.append(a);
    lista.append(item);
    return { chave, a };
  });
  nav.append(lista);
  const areaFiltros = el("div");
  cabecalho.append(titulo, nav, areaFiltros);

  const principal = el("main", { id: "principal", tabIndex: -1 });
  const rodape = el("footer");
  const fonte = el("p", { textContent: "Fonte: TSE (dados abertos), IBGE e BCB. dt_geracao: carregando…" });
  rodape.append(fonte);
  raiz.append(cabecalho, principal, rodape);

  renderFiltros(areaFiltros, store);

  const gerenciador = criarGerenciadorDeTelas(principal, TELAS_POR_CHAVE);
  // O skip link aponta para #principal; deixar o navegador mudar o hash dispararia a rota.
  document.querySelector<HTMLAnchorElement>("a.pular")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    principal.focus();
  });
  let telaAnterior: string | null = null;
  const desenhar = (e: Readonly<Estado>): void => {
    for (const { chave, a } of links) {
      a.href = `#/${chave}`;
      if (chave === e.tela) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    gerenciador.desenhar(e);
    document.title = `${TELAS_POR_CHAVE[e.tela].titulo} — Eleições 2026`;
    // Só move o foco ao trocar de tela, para leitores de tela anunciarem o novo título.
    if (telaAnterior !== null && telaAnterior !== e.tela) principal.querySelector("h1")?.focus();
    telaAnterior = e.tela;
  };
  store.assinar(desenhar);
  ligarStoreAoHash(store, window);
  desenhar(store.obter());

  criarCliente()
    .meta()
    .then((m) => { fonte.textContent = `Fonte: ${m.fonte}. dt_geracao: ${m.dt_geracao ?? "indisponível"}.`; })
    .catch(() => { fonte.textContent = "Fonte: TSE (dados abertos), IBGE e BCB. dt_geracao: indisponível (API fora do ar)."; });
}

const raiz = document.getElementById("app");
if (!raiz) throw new Error("#app não encontrado");
montar(raiz);
