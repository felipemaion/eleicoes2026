/** Busca global de candidaturas: combobox com sugestões instantâneas (`/api/busca`), atalho `/`. */
import { foiCancelada, type ClienteApi } from "../../dados/cliente";
import type { CandidaturaBusca } from "../../dados/contrato";
import type { Filtros } from "../../store";
import { criarCombobox, type ItemCombobox } from "../ui/combobox";
import { destacarTrecho, hashDaCandidatura, linhaDaSugestao, MAX_SUGESTOES, ordenarSugestoes, paramsDaBusca } from "./busca-logica";

export interface OpcoesBusca {
  cliente: ClienteApi;
  filtros: () => Pick<Filtros, "uf" | "cargo" | "ano">;
  /** Recebe o hash de destino; por padrão troca `location.hash`. */
  navegar?: (hash: string) => void;
}

const ATRASO_MS = 200;
const MIN_CARACTERES = 2;
let seq = 0;

function tecladoLivre(alvo: EventTarget | null): boolean {
  const el = alvo as HTMLElement | null;
  if (!el || el === document.body || el === document.documentElement) return true;
  return !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || el.isContentEditable);
}

function desenharItem(li: HTMLElement, c: CandidaturaBusca, consulta: string): void {
  const nome = document.createElement("span");
  nome.className = "busca-nome";
  for (const t of destacarTrecho(c.nm_urna, consulta)) {
    if (t.marca) { const m = document.createElement("mark"); m.textContent = t.texto; nome.append(m); } else nome.append(t.texto);
  }
  const contexto = document.createElement("span");
  contexto.className = "busca-contexto";
  contexto.textContent = linhaDaSugestao(c);
  li.append(nome, contexto);
}

export function render(container: HTMLElement, opcoes: OpcoesBusca): () => void {
  const navegar = opcoes.navegar ?? ((hash: string): void => { window.location.hash = hash; });
  const id = `busca-${String(++seq)}`;
  const raiz = document.createElement("div");
  raiz.className = "busca";
  const rotulo = document.createElement("label");
  rotulo.htmlFor = id;
  rotulo.className = "busca-rotulo";
  rotulo.textContent = "Buscar candidato";
  const dica = document.createElement("kbd");
  dica.className = "busca-atalho";
  dica.textContent = "/";
  dica.title = "Atalho: pressione / para buscar";
  const input = document.createElement("input");
  input.id = id;
  input.type = "search";
  input.placeholder = "Nome, número ou partido";
  input.maxLength = 80;
  const estado = document.createElement("p");
  estado.className = "busca-estado";
  estado.setAttribute("aria-live", "polite");
  raiz.append(rotulo, input, dica, estado);
  container.replaceChildren(raiz);

  let itensAtuais: CandidaturaBusca[] = [];
  const cb = criarCombobox(input, {
    rotuloLista: "Candidaturas encontradas",
    aoEscolher: (item, modo) => {
      const c = itensAtuais.find((x) => `${String(x.ano)}:${String(x.sq_candidato)}` === item.id);
      if (!c) return;
      input.value = "";
      estado.textContent = "";
      navegar(hashDaCandidatura(c, modo === "alternativo" ? "mapa" : "candidato"));
    },
  });

  let timer: ReturnType<typeof setTimeout> | undefined;
  let ctrl: AbortController | null = null;
  let minha = 0;

  function mensagem(texto: string): void { estado.textContent = texto; }

  async function buscar(q: string): Promise<void> {
    ctrl?.abort();
    const c = (ctrl = new AbortController());
    const n = ++minha;
    try {
      const r = await opcoes.cliente.busca(paramsDaBusca(q, opcoes.filtros()), c.signal);
      if (n !== minha) return;
      itensAtuais = ordenarSugestoes(r.itens, q).slice(0, MAX_SUGESTOES);
      const itens: ItemCombobox[] = itensAtuais.map((x) => ({ id: `${String(x.ano)}:${String(x.sq_candidato)}`, desenhar: (li) => { desenharItem(li, x, q); } }));
      cb.definirItens(itens);
      if (itens.length === 0) { mensagem(`Nenhum candidato encontrado para “${q}”. Tente só o sobrenome ou o número de urna.`); return; }
      cb.abrir();
      mensagem(r.total > itens.length ? `${String(itens.length)} de ${String(r.total)} resultados — refine a busca.` : `${String(itens.length)} ${itens.length === 1 ? "resultado" : "resultados"}.`);
    } catch (e) {
      if (foiCancelada(e) || n !== minha) return;
      console.error("Busca indisponível:", e);
      cb.definirItens([]);
      mensagem("Busca indisponível no momento. Tente de novo em instantes.");
    }
  }

  const aoDigitar = (): void => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < MIN_CARACTERES) {
      ctrl?.abort();
      minha += 1;
      cb.definirItens([]);
      mensagem(q.length === 0 ? "" : "Digite pelo menos 2 caracteres.");
      return;
    }
    mensagem("Buscando…");
    timer = setTimeout(() => { void buscar(q); }, ATRASO_MS);
  };
  input.addEventListener("input", aoDigitar);

  const aoAtalho = (e: KeyboardEvent): void => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || !tecladoLivre(e.target)) return;
    e.preventDefault();
    input.focus();
    input.select();
  };
  document.addEventListener("keydown", aoAtalho);

  return () => {
    clearTimeout(timer);
    ctrl?.abort();
    document.removeEventListener("keydown", aoAtalho);
    input.removeEventListener("input", aoDigitar);
    cb.destruir();
    container.replaceChildren();
  };
}
