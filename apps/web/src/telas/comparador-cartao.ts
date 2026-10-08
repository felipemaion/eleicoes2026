/**
 * Cartão de um lado do comparador (2022 ou 2026): mostra o que está escolhido em uma linha e,
 * em "Alterar", abre o editor: um grupo da configuração OU candidatos achados por busca com chips.
 * Nunca lista todos os nomes: só até 8 sugestões enquanto o usuário digita.
 */
import { foiCancelada, type ClienteApi } from "../dados/cliente";
import { alternarCandidato, type GrupoConfig, type Lado } from "../dados/comparador-logica";
import type { CandidaturaBusca } from "../dados/contrato";
import { destacarTrecho, LIMITE_BUSCA, linhaDaSugestao, MAX_SUGESTOES, ordenarSugestoes } from "../componentes/busca/busca-logica";
import { criarCombobox, type ItemCombobox } from "../componentes/ui/combobox";
import { figuraCandidato } from "../componentes/ui/foto-candidato";
import { h } from "./dom";
import { TEXTOS_COMPARADOR as T } from "../textos";

export interface OpcoesCartao {
  ano: 2022 | 2026;
  cliente: ClienteApi;
  /** Só os grupos deste ano. */
  grupos: readonly GrupoConfig[];
  lado: Lado;
  /** Texto de uma linha do que o lado contém. */
  nome: string;
  /** `sq` → nome de urna, compartilhado com a tela (chips e frase-resumo). */
  nomes: Map<string, string>;
  /** `sq` das candidaturas indicadas pelo grupo (selo nos chips e sugestões); a tela e o cartão completam. */
  indicados: Set<string>;
  /** Cargo e UF já no formato da API (`uf` "BR" = sem filtro). */
  cargo: string;
  uf: string;
  /** Mensagem curta do lado (ex.: 422 da API). */
  erro?: string | undefined;
  aplicar(lado: Lado): void;
}

const ATRASO_MS = 200;
const MIN_CARACTERES = 2;
let seq = 0;

export function criarCartao(container: HTMLElement, o: OpcoesCartao): () => void {
  const id = `cartao-${String(o.ano)}-${String(++seq)}`;
  let modo: "grupo" | "candidatos" = o.lado.tipo;
  let grupo = o.lado.tipo === "grupo" ? o.lado.id : (o.grupos[0]?.id ?? "");
  let sqs: string[] = o.lado.tipo === "candidatos" ? [...o.lado.sqs] : [];
  const sugestoes = new Map<string, CandidaturaBusca>();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let ctrl: AbortController | null = null;
  let geracao = 0;

  const alterar = h("button", { type: "button", textContent: T.alterar });
  alterar.dataset["acao"] = "alterar";
  alterar.setAttribute("aria-expanded", "false");
  alterar.setAttribute("aria-controls", `${id}-editor`);
  const resumo = h("p", { className: "cartao-resumo", textContent: o.nome });

  const radio = (valor: "grupo" | "candidatos", rotulo: string): { rotulo: HTMLLabelElement; input: HTMLInputElement } => {
    const input = h("input", { type: "radio", name: `${id}-modo`, value: valor, checked: modo === valor });
    input.addEventListener("click", () => { modo = valor; desenharModo(); });
    return { rotulo: h("label", { className: "rotulo-linha" }, input, rotulo), input };
  };
  const rGrupo = radio("grupo", T.modoGrupo);
  const rCand = radio("candidatos", T.modoCandidatos);

  const select = h("select", { name: "grupo" });
  for (const g of o.grupos) select.add(new Option(g.rotulo, g.id));
  select.value = grupo;
  select.addEventListener("change", () => { grupo = select.value; });
  const notaGrupo = h("p", { className: "nota" });
  const mostrarNotaGrupo = (): void => { notaGrupo.textContent = T.notaGrupo[grupo] ?? ""; };
  select.addEventListener("change", mostrarNotaGrupo);
  mostrarNotaGrupo();
  const painelGrupo = h("div", { className: "cartao-painel" }, h("label", {}, T.grupoRotulo, select), notaGrupo);
  const selo = (): HTMLElement => h("span", { className: "selo", textContent: T.seloIndicado });

  const campo = h("input", { type: "search", id: `${id}-q`, placeholder: T.placeholderBusca, maxLength: 80 });
  const estado = h("p", { className: "nota" });
  estado.setAttribute("aria-live", "polite");
  const chips = h("ul", { className: "chips-candidatos" });
  const painelCand = h("div", { className: "cartao-painel" }, h("label", { htmlFor: `${id}-q` }, T.buscaRotulo), campo, estado, chips);

  const aplicar = h("button", { type: "button", textContent: T.aplicar });
  aplicar.dataset["acao"] = "aplicar";
  const cancelar = h("button", { type: "button", textContent: T.cancelar });
  cancelar.dataset["acao"] = "cancelar";
  const editor = h("div", { className: "cartao-editor", id: `${id}-editor`, hidden: true },
    h("div", { className: "cartao-modos", role: "group" }, rGrupo.rotulo, rCand.rotulo), painelGrupo, painelCand,
    h("div", { className: "atalhos" }, aplicar, cancelar));
  editor.querySelector<HTMLElement>(".cartao-modos")?.setAttribute("aria-label", T.modoRotulo);

  const erro = o.erro ? [h("p", { className: "cartao-erro", textContent: o.erro, role: "alert" })] : [];
  container.replaceChildren(h("section", { className: "cartao-lado" },
    h("h2", { textContent: String(o.ano) }), resumo, alterar, ...erro, editor));

  const cb = criarCombobox(campo, {
    rotuloLista: T.sugestoesRotulo,
    aoEscolher: (item) => {
      const c = sugestoes.get(item.id);
      if (!c) return;
      const sq = String(c.sq_candidato);
      o.nomes.set(sq, c.nm_urna);
      if (c.indicado) o.indicados.add(sq);
      sqs = alternarCandidato(sqs, sq);
      campo.value = "";
      estado.textContent = "";
      cb.definirItens([]);
      desenharChips();
    },
  });

  function desenharChips(): void {
    chips.replaceChildren(...sqs.map((sq) => {
      const nome = o.nomes.get(sq) ?? `candidato ${sq}`;
      const x = h("button", { type: "button", textContent: "×" });
      x.setAttribute("aria-label", `Remover ${nome}`);
      x.addEventListener("click", () => { sqs = sqs.filter((s) => s !== sq); desenharChips(); });
      return h("li", { className: "chip-candidato" }, nome, ...(o.indicados.has(sq) ? [selo()] : []), x);
    }));
    aplicar.disabled = modo === "candidatos" && sqs.length === 0;
  }
  function desenharModo(): void {
    painelGrupo.hidden = modo !== "grupo";
    painelCand.hidden = modo !== "candidatos";
    desenharChips();
  }

  async function buscar(q: string): Promise<void> {
    ctrl?.abort();
    const c = (ctrl = new AbortController());
    const minha = ++geracao;
    try {
      const r = await o.cliente.busca({ q, ano: String(o.ano), cargo: o.cargo, ...(o.uf !== "BR" ? { uf: o.uf } : {}), limite: String(LIMITE_BUSCA) }, c.signal);
      if (minha !== geracao) return;
      const itens = ordenarSugestoes(r.itens, q).filter((x) => !sqs.includes(String(x.sq_candidato))).slice(0, MAX_SUGESTOES);
      sugestoes.clear();
      const lista: ItemCombobox[] = itens.map((x) => {
        const chave = String(x.sq_candidato);
        sugestoes.set(chave, x);
        return {
          id: chave,
          desenhar: (li) => {
            const nome = h("span", { className: "busca-nome" });
            for (const t of destacarTrecho(x.nm_urna, q)) nome.append(t.marca ? h("mark", { textContent: t.texto }) : t.texto);
            li.append(figuraCandidato(x.nm_urna, x.foto_url, 32, 40), h("span", { className: "busca-textos" }, nome, ...(x.indicado ? [selo()] : []), h("span", { className: "busca-contexto", textContent: linhaDaSugestao(x) })));
          },
        };
      });
      cb.definirItens(lista);
      if (lista.length === 0) { estado.textContent = T.semResultado(q); return; }
      cb.abrir();
      estado.textContent = r.total > lista.length ? T.refine(lista.length, r.total) : "";
    } catch (e) {
      if (foiCancelada(e) || minha !== geracao) return;
      console.error("Busca indisponível:", e);
      cb.definirItens([]);
      estado.textContent = T.buscaIndisponivel;
    }
  }
  campo.addEventListener("input", () => {
    clearTimeout(timer);
    const q = campo.value.trim();
    if (q.length < MIN_CARACTERES) { ctrl?.abort(); geracao += 1; cb.definirItens([]); estado.textContent = q.length === 0 ? "" : T.minimo; return; }
    estado.textContent = T.buscando;
    timer = setTimeout(() => { void buscar(q); }, ATRASO_MS);
  });

  const abrirEditor = (abrir: boolean): void => {
    editor.hidden = !abrir;
    alterar.setAttribute("aria-expanded", abrir ? "true" : "false");
    if (abrir) { desenharModo(); (modo === "grupo" ? select : campo).focus(); } else { cb.fechar(); alterar.focus(); }
  };
  alterar.addEventListener("click", () => { abrirEditor(editor.hidden === true); });
  cancelar.addEventListener("click", () => {
    modo = o.lado.tipo;
    grupo = o.lado.tipo === "grupo" ? o.lado.id : (o.grupos[0]?.id ?? "");
    sqs = o.lado.tipo === "candidatos" ? [...o.lado.sqs] : [];
    select.value = grupo;
    mostrarNotaGrupo();
    (modo === "grupo" ? rGrupo : rCand).input.checked = true;
    abrirEditor(false);
  });
  aplicar.addEventListener("click", () => { o.aplicar(modo === "grupo" ? { tipo: "grupo", id: grupo } : { tipo: "candidatos", sqs: [...sqs] }); });

  return () => { clearTimeout(timer); ctrl?.abort(); cb.destruir(); container.replaceChildren(); };
}
