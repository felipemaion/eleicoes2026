/**
 * Filtros: ano e cargo como segmentos, UF com busca, grupo com descrição, contagem ao vivo e
 * "Limpar". O estado vive no store (e, por ele, no hash); nada recarrega a página.
 */
import { criarCliente, foiCancelada, type ClienteApi } from "../../dados/cliente";
import { cargoDaApi, paramsDeFiltros } from "../../dados/adaptadores";
import { cargoNacional, contagemTexto, opcoesDeUf, resumoDeGrupo, rotuloDaUf, ROTULO_CARGO } from "../../filtros-logica";
import { ANOS, CARGOS, FILTROS_PADRAO, type Filtros, type Store, type Uf } from "../../store";
import type { Grupo } from "../../dados/contrato";
import { criarCombobox } from "../ui/combobox";

let seq = 0;

function criar<K extends keyof HTMLElementTagNameMap>(tag: K, props: Partial<HTMLElementTagNameMap[K]> = {}, ...filhos: (Node | string)[]): HTMLElementTagNameMap[K] {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...filhos);
  return e;
}

/** Grupo de rádios estilizado como chips: navegação por setas e leitura de "n de N" de graça. */
function segmentos<V extends string | number>(
  nome: string, legenda: string, opcoes: readonly { valor: V; texto: string }[], aoEscolher: (v: V) => void,
): { campo: HTMLFieldSetElement; marcar(v: V): void } {
  const campo = criar("fieldset", { className: "filtro-segmentos" }, criar("legend", { textContent: legenda }));
  const roda = criar("div", { className: "chips" });
  const inputs = opcoes.map((o) => {
    const id = `f-${nome}-${String(++seq)}`;
    const input = criar("input", { type: "radio", name: nome, id, value: String(o.valor) });
    input.addEventListener("change", () => { if (input.checked) aoEscolher(o.valor); });
    roda.append(input, criar("label", { htmlFor: id, textContent: o.texto }));
    return { input, valor: o.valor };
  });
  campo.append(roda);
  return { campo, marcar: (v) => { for (const i of inputs) i.input.checked = i.valor === v; } };
}

const igualAoPadrao = (f: Filtros): boolean => (Object.keys(FILTROS_PADRAO) as (keyof Filtros)[]).every((k) => f[k] === FILTROS_PADRAO[k]);

export function render(container: HTMLElement, store: Store, cliente: ClienteApi = criarCliente()): () => void {
  const form = criar("form", { className: "filtros" });
  form.setAttribute("aria-label", "Filtros");
  form.addEventListener("submit", (e) => { e.preventDefault(); });

  const ano = segmentos("ano", "Ano da eleição", ANOS.map((a) => ({ valor: a, texto: String(a) })), (a) => { store.definir({ ano: a }); });
  const cargo = segmentos("cargo", "Cargo", CARGOS.map((c) => ({ valor: c, texto: ROTULO_CARGO[c] })), (c) => { store.definir({ cargo: c }); });

  const idUf = `f-uf-${String(++seq)}`;
  const inputUf = criar("input", { id: idUf, name: "uf", type: "text", placeholder: "Brasil ou digite o estado" });
  const dicaUf = criar("small", { className: "filtro-dica" });
  const campoUf = criar("div", { className: "filtro-uf" }, criar("label", { htmlFor: idUf, textContent: "Estado (UF)" }), inputUf, dicaUf);
  // UFs com candidatura no recorte (grupo + cargo); `undefined` enquanto a API não respondeu.
  let ufsDisponiveis: ReadonlySet<string> | undefined;
  let opcoesUf = opcoesDeUf("");
  const cbUf = criarCombobox(inputUf, {
    rotuloLista: "Estados",
    aoEscolher: (item) => { store.definir({ uf: item.id as Uf }); },
  });
  const listarUfs = (consulta: string): void => {
    opcoesUf = opcoesDeUf(consulta, ufsDisponiveis);
    cbUf.definirItens(opcoesUf.map((o) => ({ id: o.valor, desenhar: (li) => { li.textContent = o.texto; } })));
  };
  inputUf.addEventListener("input", () => { listarUfs(inputUf.value); cbUf.abrir(); });
  // Ao focar, mostra todas as opções: o campo mostra o valor atual, mas a lista começa completa.
  inputUf.addEventListener("focus", () => { inputUf.select(); listarUfs(""); cbUf.abrir(); });
  // Sair sem escolher devolve o texto ao valor real do filtro.
  inputUf.addEventListener("blur", () => { inputUf.value = rotuloDaUf(store.obter().filtros.uf); });

  const idGrupo = `f-grupo-${String(++seq)}`;
  const selGrupo = criar("select", { id: idGrupo, name: "grupo" });
  // Opções vêm de /api/grupos (DRY com config/grupos.yaml); até responder, só o grupo atual.
  let gruposApi: readonly Grupo[] = [];
  selGrupo.addEventListener("change", () => { if (selGrupo.value) store.definir({ grupo: selGrupo.value }); });
  const desenharGrupos = (atual: string): void => {
    const opcoes = gruposApi.map((g) => new Option(g.rotulo, g.id));
    // Grupo vindo da URL e desconhecido da API continua visível em vez de sumir em silêncio.
    if (!gruposApi.some((g) => g.id === atual)) opcoes.unshift(new Option(atual, atual));
    selGrupo.replaceChildren(...opcoes);
    selGrupo.value = atual;
  };
  const descGrupo = criar("small", { className: "filtro-grupo-desc filtro-dica" });
  const campoGrupo = criar("div", { className: "filtro-grupo" }, criar("label", { htmlFor: idGrupo, textContent: "Grupo comparado" }), selGrupo, descGrupo);

  const contagem = criar("p", { className: "filtros-contagem" });
  contagem.setAttribute("aria-live", "polite");
  const limpar = criar("button", { type: "button", className: "filtros-limpar", textContent: "Limpar filtros" });
  limpar.addEventListener("click", () => { store.definir({ ...FILTROS_PADRAO }); });
  form.append(ano.campo, cargo.campo, campoUf, campoGrupo, contagem, limpar);

  let timer: ReturnType<typeof setTimeout> | undefined;
  let ctrl: AbortController | null = null;
  let chaveContada = "";

  function contar(f: Filtros): void {
    // Só o recorte importa: mudar a tela ou o candidato fixado não refaz a contagem.
    const chave = [f.ano, f.grupo, f.cargo, f.uf].join("|");
    if (chave === chaveContada) return;
    chaveContada = chave;
    clearTimeout(timer);
    ctrl?.abort();
    contagem.textContent = "Contando…";
    timer = setTimeout(() => {
      const c = (ctrl = new AbortController());
      cliente.candidatos({ ...paramsDeFiltros(f), limite: "1" }, c.signal).then(
        (r) => { contagem.textContent = contagemTexto(r.total); },
        (e: unknown) => { if (!foiCancelada(e)) { console.error("Contagem indisponível:", e); contagem.textContent = ""; } },
      );
    }, 250);
  }

  let ctrlUfs: AbortController | null = null;
  let chaveUfs = "";
  function carregarUfs(f: Filtros): void {
    // Presidente não tem UF; o recorte das UFs depende só de grupo e cargo.
    if (cargoNacional(f.cargo)) { chaveUfs = ""; ufsDisponiveis = undefined; return; }
    const chave = `${f.grupo}|${f.cargo}`;
    if (chave === chaveUfs) return;
    chaveUfs = chave;
    ctrlUfs?.abort();
    const c = (ctrlUfs = new AbortController());
    cliente.ufs({ grupo: f.grupo, cargo: cargoDaApi(f.cargo) }, c.signal).then(
      (r) => {
        ufsDisponiveis = new Set(r.itens.map((i) => i.uf));
        // Dependência: a UF escolhida não tem candidatura neste cargo → volta ao Brasil em vez de mostrar tela vazia.
        const atual = store.obter().filtros.uf;
        if (atual !== "BR" && !ufsDisponiveis.has(atual)) store.definir({ uf: "BR" });
      },
      (e: unknown) => { if (!foiCancelada(e)) { chaveUfs = ""; console.error("UFs do recorte indisponíveis:", e); } },
    );
  }

  const sincronizar = (): void => {
    const { filtros } = store.obter();
    ano.marcar(filtros.ano);
    cargo.marcar(filtros.cargo);
    if (document.activeElement !== inputUf) inputUf.value = rotuloDaUf(filtros.uf);
    const travada = cargoNacional(filtros.cargo);
    inputUf.disabled = travada;
    dicaUf.textContent = travada ? "Presidente é eleição nacional: o recorte é o Brasil inteiro." : "";
    if (selGrupo.value !== filtros.grupo || selGrupo.options.length === 0) desenharGrupos(filtros.grupo);
    descGrupo.textContent = resumoDeGrupo(gruposApi.find((g) => g.id === filtros.grupo));
    limpar.hidden = igualAoPadrao(filtros);
    contar(filtros);
    carregarUfs(filtros);
  };
  sincronizar();
  const ctrlGrupos = new AbortController();
  cliente.grupos(ctrlGrupos.signal).then(
    (r) => { gruposApi = r.grupos; desenharGrupos(store.obter().filtros.grupo); sincronizar(); },
    (e: unknown) => { if (!foiCancelada(e)) console.error("Grupos indisponíveis:", e); },
  );
  const cancelar = store.assinar(sincronizar);
  container.replaceChildren(form);
  return () => { cancelar(); clearTimeout(timer); ctrl?.abort(); ctrlUfs?.abort(); ctrlGrupos.abort(); cbUf.destruir(); container.replaceChildren(); };
}
