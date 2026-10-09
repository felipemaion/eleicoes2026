import "./tokens.css";
import "./estilo.css";
import { render as renderBusca } from "./componentes/busca/busca";
import { ligarCabecalhoMovel } from "./componentes/ui/cabecalho-movel";
import { render as renderFiltros } from "./componentes/filtros/filtros";
import { criarCliente } from "./dados/cliente";
import { ROTULO_CARGO } from "./filtros-logica";
import { definirAjustadorDeRecorte } from "./telas/recorte";
import { criarSobreposicao, definirSobreposicaoGlobal } from "./componentes/ui/sobreposicao";
import { cssDasCores, TEMAS } from "./paletas";
import { ligarStoreAoHash, rotaExiste, ROTULOS_TELA } from "./rotas";
import { criarStore, TELAS, type Estado } from "./store";
import { TELAS_POR_CHAVE } from "./telas";
import { criarGerenciadorDeTelas } from "./telas/ciclo";

const FONTES = "Fontes: TSE (dados abertos), IBGE e BCB.";
const REPOSITORIO = "https://github.com/felipemaion/eleicoes2026";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, props: Partial<HTMLElementTagNameMap[K]> = {}): HTMLElementTagNameMap[K] {
  return Object.assign(document.createElement(tag), props);
}

const CHAVE_TEMA = "eleicoes2026:tema";

/** Tema escuro (identidade Missão) é o padrão; o claro é escolha explícita, lembrada neste navegador. */
function ligarTema(botao: HTMLButtonElement): void {
  const aplicar = (claro: boolean): void => {
    if (claro) document.documentElement.dataset["tema"] = "claro";
    else delete document.documentElement.dataset["tema"];
    botao.setAttribute("aria-pressed", String(claro));
    botao.textContent = claro ? "Tema escuro" : "Tema claro";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", (claro ? TEMAS.claro : TEMAS.escuro).fundo);
    window.dispatchEvent(new Event("tema-alterado"));
  };
  let salvo = false;
  try { salvo = window.localStorage.getItem(CHAVE_TEMA) === "claro"; } catch { /* armazenamento bloqueado: segue no padrão */ }
  aplicar(salvo);
  botao.addEventListener("click", () => {
    const claro = document.documentElement.dataset["tema"] !== "claro";
    aplicar(claro);
    try { window.localStorage.setItem(CHAVE_TEMA, claro ? "claro" : "escuro"); } catch { /* sem persistência */ }
  });
}

function montar(raiz: HTMLElement): void {
  const estilo = el("style");
  estilo.textContent = cssDasCores();
  document.head.append(estilo);

  const store = criarStore();
  const cabecalho = el("header", { className: "topo" });
  const marca = el("h2", { className: "marca-site" });
  marca.append(el("span", { className: "selo", textContent: "14" }), "Eleições 2026", el("span", { className: "sub", textContent: " · Partido Missão" }));
  const nav = el("nav");
  nav.setAttribute("aria-label", "Telas");
  const lista = el("ul");
  const itens = TELAS.map((chave) => {
    const a = el("a", { textContent: ROTULOS_TELA[chave] });
    const item = el("li");
    item.append(a);
    lista.append(item);
    return { chave, a };
  });
  nav.append(lista);
  const botaoTema = el("button", { type: "button", className: "tema-botao" });
  const slotBusca = el("div", { className: "busca-slot" });
  // Painel do menu: no desktop é transparente (display: contents); no celular abre pelo ☰ com "Tema" dentro.
  const painelMenu = el("div", { className: "menu-painel", id: "menu-painel" });
  painelMenu.append(nav, botaoTema);
  const botaoBusca = el("button", { type: "button", className: "botao-topo botao-busca" });
  botaoBusca.setAttribute("aria-label", "Buscar");
  botaoBusca.setAttribute("aria-expanded", "false");
  botaoBusca.setAttribute("aria-controls", "busca-slot");
  botaoBusca.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M15 15l6 6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>';
  const botaoMenu = el("button", { type: "button", className: "botao-topo botao-menu" });
  botaoMenu.setAttribute("aria-label", "Menu");
  botaoMenu.setAttribute("aria-expanded", "false");
  botaoMenu.setAttribute("aria-controls", "menu-painel");
  botaoMenu.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>';
  slotBusca.id = "busca-slot";
  cabecalho.append(marca, slotBusca, botaoBusca, botaoMenu, painelMenu);
  ligarCabecalhoMovel({ cabecalho, botaoMenu, painelMenu, botaoBusca, slotBusca });
  ligarTema(botaoTema);
  const lateral = el("aside", { className: "lateral" });
  lateral.setAttribute("aria-label", "Filtros");
  const areaFiltros = el("div", { id: "area-filtros" });
  // Só no celular: sem o botão os filtros ocupam a primeira tela inteira e empurram o conteúdo para baixo.
  const alternar = el("button", { type: "button", className: "lateral-alternar" });
  alternar.setAttribute("aria-controls", "area-filtros");
  alternar.setAttribute("aria-expanded", "false");
  alternar.addEventListener("click", () => {
    const aberto = lateral.dataset["aberto"] !== "sim";
    lateral.dataset["aberto"] = aberto ? "sim" : "nao";
    alternar.setAttribute("aria-expanded", String(aberto));
  });
  lateral.dataset["aberto"] = "nao";
  const fecharFiltros = (devolverFoco: boolean): void => {
    if (lateral.dataset["aberto"] !== "sim") return;
    lateral.dataset["aberto"] = "nao";
    alternar.setAttribute("aria-expanded", "false");
    if (devolverFoco) alternar.focus();
  };
  // Esc fecha o painel, mas só depois de a lista de UF (combobox) ter tratado o seu próprio Esc.
  lateral.addEventListener("keydown", (ev) => {
    const alvo = ev.target instanceof HTMLElement ? ev.target : null;
    if (ev.key === "Escape" && (alvo === alternar || alvo?.getAttribute("aria-expanded") !== "true")) fecharFiltros(true);
  });
  document.addEventListener("pointerdown", (ev) => {
    if (ev.target instanceof Node && !lateral.contains(ev.target)) fecharFiltros(false);
  });
  lateral.append(el("h2", { textContent: "Filtros" }), alternar, areaFiltros);

  const principal = el("main", { id: "principal", tabIndex: -1 });
  const rodape = el("footer");
  const fonte = el("p", { textContent: `${FONTES} dt_geracao: carregando…` });
  const links = el("p");
  const aMetodologia = el("a", { textContent: "Metodologia", href: "#/como-ler" });
  const aRepo = el("a", { textContent: "Código no GitHub", href: REPOSITORIO, rel: "noopener" });
  links.append(aMetodologia, " · ", aRepo);
  rodape.append(fonte, links);
  const corpo = el("div", { className: "corpo" });
  corpo.append(lateral, principal);
  raiz.classList.add("app");
  raiz.append(cabecalho, corpo, rodape);
  definirSobreposicaoGlobal(criarSobreposicao(document.body, principal));

  const clienteBusca = criarCliente();
  renderFiltros(areaFiltros, store, clienteBusca);
  renderBusca(slotBusca, { cliente: clienteBusca, filtros: () => store.obter().filtros });

  const gerenciador = criarGerenciadorDeTelas(principal, TELAS_POR_CHAVE);
  // O skip link aponta para #principal; deixar o navegador mudar o hash dispararia a rota.
  document.querySelector<HTMLAnchorElement>("a.pular")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    principal.focus();
  });
  let telaAnterior: string | null = null;
  let em404 = false;
  const desenhar = (e: Readonly<Estado>, ajuste = false): void => {
    // Ajuste de recorte (filtros seguindo o candidato) não refaz a tela: ela já está desenhada com esse candidato.
    if (em404 || ajuste) return;
    for (const { chave, a } of itens) {
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
  definirAjustadorDeRecorte((f) => { store.ajustar(f); });
  const resumo = (e: Readonly<Estado>): void => {
    const f = e.filtros;
    alternar.textContent = `Filtros: ${ROTULO_CARGO[f.cargo]} · ${f.uf === "BR" ? "Brasil" : f.uf} · ${String(f.ano)} ▾`;
  };
  resumo(store.obter());
  store.assinar(resumo);
  store.assinar(desenhar);
  ligarStoreAoHash(store, window);

  // Rota de hash desconhecida: página 404 com saída para a visão geral (o estado da store não muda).
  const verificarRota = (): boolean => {
    const existe = rotaExiste(window.location.hash);
    if (!existe && !em404) {
      em404 = true;
      gerenciador.destruir();
      telaAnterior = null;
      const h1 = el("h1", { textContent: "Página não encontrada", tabIndex: -1 });
      const voltar = el("a", { textContent: "Ir para a visão geral", href: "#/visao-geral" });
      principal.replaceChildren(h1, el("p", { textContent: `Não existe a tela "${window.location.hash.slice(2).split("?")[0] ?? ""}". ` }), voltar);
      document.title = "Página não encontrada — Eleições 2026";
      h1.focus();
    } else if (existe && em404) {
      em404 = false;
      desenhar(store.obter());
    }
    return existe;
  };
  window.addEventListener("hashchange", verificarRota);
  if (verificarRota()) desenhar(store.obter());

  criarCliente()
    .meta()
    .then((m) => { fonte.textContent = `${FONTES} dt_geracao: ${m.dt_geracao}.`; })
    .catch(() => { fonte.textContent = `${FONTES} dt_geracao: indisponível (API fora do ar).`; });
}

const raiz = document.getElementById("app");
if (!raiz) throw new Error("#app não encontrado");
montar(raiz);
