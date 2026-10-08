/** Seletor de candidatos da Evolução: busca por nome, "só indicados", atalhos e rascunho da seleção. */
import { alternarPessoa, idsDe, soIndicados } from "../dados/evolucao-logica";
import type { ClienteApi, Params } from "../dados/cliente";
import type { PessoaEvolucao } from "../dados/contrato";
import { formatarNumero } from "../formato";
import { h } from "./dom";

export interface OpcoesSelecao {
  cliente: ClienteApi;
  /** Cargo/UF da barra de filtros, já no formato da API; mesmos da comparação. */
  params: Params;
  /** Descrição humana do recorte ("Deputado federal · Sergipe (SE)"). */
  recorte: string;
  /** Seleção atual (a que está no hash). */
  selecionadas: readonly string[];
  /** Grava a seleção (ids) no hash; lista vazia volta ao grupo inteiro. */
  aplicar(ids: string[]): void;
}

const ATRASO_MS = 300;
const LIMITE = "200";
let seq = 0;

function contexto(p: PessoaEvolucao): string {
  const lado = (c: PessoaEvolucao["de"]): string => `${String(c.ano)} · ${c.partido.sigla} · ${c.cargo.toLowerCase()} · ${c.uf} · ${formatarNumero(c.votos)} votos`;
  return `${lado(p.de)}  →  ${lado(p.para)}`;
}

export function criarSelecao(container: HTMLElement, o: OpcoesSelecao): () => void {
  const id = `pessoas-${String(++seq)}`;
  let rascunho = [...o.selecionadas];
  let consulta = "";
  let soInd = false;
  let itens: readonly PessoaEvolucao[] = [];
  let vivo = true;
  let geracao = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const campo = h("input", { type: "search", name: "busca-pessoas", id: `${id}-q`, placeholder: "Nome do candidato", maxLength: 80 });
  const caixaInd = h("input", { type: "checkbox", name: "so-indicados" });
  const estado = h("p", { className: "nota selecao-estado" });
  estado.setAttribute("aria-live", "polite");
  const contagem = h("span", { className: "selecao-contagem" });
  const lista = h("ul", { className: "lista-pessoas" });
  const mk = (rotulo: string, acao: string, extra: Partial<HTMLButtonElement> = {}): HTMLButtonElement => {
    const b = h("button", { type: "button", textContent: rotulo, ...extra });
    b.dataset["acao"] = acao;
    return b;
  };
  const comparar = mk("Comparar selecionados", "comparar");
  const limpar = mk("Limpar escolha", "limpar");
  const grupo = h("button", { type: "button", textContent: "Grupo inteiro" });
  grupo.dataset["atalho"] = "grupo";
  const indicados = h("button", { type: "button", textContent: "Só indicados" });
  indicados.dataset["atalho"] = "indicados";

  const visiveis = (): PessoaEvolucao[] => (soInd ? soIndicados(itens) : [...itens]);

  function desenharLista(): void {
    const v = visiveis();
    lista.replaceChildren(...v.map((p) => {
      const caixa = h("input", { type: "checkbox", value: p.pessoa_id_publico, checked: rascunho.includes(p.pessoa_id_publico), disabled: !p.comparavel });
      caixa.addEventListener("change", () => { rascunho = alternarPessoa(rascunho, p.pessoa_id_publico); atualizarContagem(); });
      const nome = h("strong", { textContent: p.nome });
      const ind = p.de.indicado || p.para.indicado ? [h("span", { className: "selo", textContent: "indicado" })] : [];
      const corpo = h("span", { className: "pessoa-texto" }, nome, ...ind, h("span", { className: "pessoa-contexto", textContent: contexto(p) }));
      const motivo = p.comparavel ? [] : [h("span", { className: "nota", textContent: "Fora do comparativo: não concorreu ao mesmo cargo nos dois anos (ou é Senado, cujo voto não se compara)." })];
      return h("li", { className: "pessoa-item" }, h("label", {}, caixa, corpo), ...motivo);
    }));
    estado.textContent = v.length === 0 ? "Nenhuma pessoa encontrada com estes filtros." : `${formatarNumero(v.length)} ${v.length === 1 ? "pessoa" : "pessoas"} na lista${itens.length >= Number(LIMITE) ? " (mostrando as primeiras; refine a busca)" : ""}.`;
  }
  function atualizarContagem(): void {
    contagem.textContent = `${String(rascunho.length)} ${rascunho.length === 1 ? "selecionado" : "selecionados"}`;
    comparar.disabled = rascunho.length === 0;
    limpar.disabled = rascunho.length === 0;
  }

  async function buscar(): Promise<void> {
    const minha = ++geracao;
    estado.textContent = "Buscando…";
    try {
      const r = await o.cliente.pessoas({ ...o.params, ...(consulta.trim().length >= 2 ? { q: consulta.trim() } : {}), limite: LIMITE });
      if (!vivo || minha !== geracao) return;
      itens = r.itens;
      desenharLista();
    } catch (e) {
      if (!vivo || minha !== geracao) return;
      console.error("Falha ao listar pessoas:", e);
      estado.textContent = "Não foi possível carregar a lista de candidatos agora. Tente de novo em instantes.";
      estado.setAttribute("role", "alert");
    }
  }

  campo.addEventListener("input", () => {
    consulta = campo.value;
    clearTimeout(timer);
    // Uma letra só devolveria quase todos: espera 2+ caracteres (ou campo vazio) e debounce.
    if (consulta.trim().length === 1) return;
    timer = setTimeout(() => { void buscar(); }, ATRASO_MS);
  });
  caixaInd.addEventListener("change", () => { soInd = caixaInd.checked; desenharLista(); });
  comparar.addEventListener("click", () => { o.aplicar(rascunho); });
  limpar.addEventListener("click", () => { rascunho = []; desenharLista(); atualizarContagem(); });
  grupo.addEventListener("click", () => { o.aplicar([]); });
  indicados.addEventListener("click", () => { o.aplicar(idsDe(soIndicados(itens))); });

  container.replaceChildren(h("section", { className: "selecao-pessoas" },
    h("h2", { textContent: "Escolha os candidatos" }),
    h("p", { className: "nota", textContent: `Recorte: ${o.recorte}. Mude cargo e UF na barra de filtros. Marque quem quer ver lado a lado e clique em “Comparar selecionados”.` }),
    h("div", { className: "controles" },
      h("label", { htmlFor: `${id}-q` }, "Buscar por nome", campo),
      h("label", { className: "rotulo-linha" }, caixaInd, "Mostrar só indicados"),
    ),
    h("div", { className: "atalhos" }, grupo, indicados, comparar, limpar, contagem),
    estado, lista,
  ));
  atualizarContagem();
  void buscar();
  return () => { vivo = false; clearTimeout(timer); container.replaceChildren(); };
}
