import { criarCliente, ErroApi, type ClienteApi } from "../dados/cliente";
import type { RespostaReferencias } from "../dados/contrato";
import {
  BLOCOS, blocoInicial, buscarNossos, escolherNosso, hashDaFicha, linhasDaTabela, paramsReferencias, pontosDeIndice, ufInicial,
  type BlocoId, type CandidatoRef, type Celula,
} from "../dados/referencias-logica";
import { blocoReferencia, textoReferencia } from "../textos";
import { render as renderIndice } from "../componentes/graficos/indice-mediana";
import { figuraCandidato } from "../componentes/ui/foto-candidato";
import { corpoRico, criarFlutuante, ligarMarca, type Flutuante } from "../componentes/ui/tooltip";
import { formatarNumero } from "../formato";
import { UFS } from "../store";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

type Carga = { tipo: "ok"; dados: RespostaReferencias } | { tipo: "indisponivel"; mensagem: string };
type Contexto = Parameters<typeof ajuda>[1];

const MSG_422 = "Este cargo ou esta UF não tem grupo de referência para comparar.";
const N_ESPERADO = 5;

/** 422 (cargo/UF sem referência) é resposta legítima da API: vira aviso, não "tente novamente". */
async function buscar(cliente: ClienteApi, params: Record<string, string>): Promise<Carga> {
  try {
    return { tipo: "ok", dados: await cliente.referencias(params) };
  } catch (e) {
    if (e instanceof ErroApi && e.status === 422) return { tipo: "indisponivel", mensagem: MSG_422 };
    throw e;
  }
}

let balao: Flutuante | null = null;
/** Um balão para toda a aba (o componente de tooltip reposiciona dentro da janela). */
function tooltip(): Flutuante {
  if (!balao?.elemento.isConnected) balao = criarFlutuante();
  return balao;
}

function cartao(c: CandidatoRef): Node {
  return corpoRico({
    titulo: c.nm_urna,
    foto: { nome: c.nm_urna, url: c.foto_url },
    linhas: [
      ["Partido", `${c.partido.sigla} (${String(c.partido.numero)})`],
      ["UF", c.sg_uf],
      ["Resultado", c.resultado ?? "sem apuração"],
      ["Votos", formatarNumero(c.votos)],
    ],
    rodape: ["Clique para abrir a ficha."],
  });
}

/** Cabeçalho de coluna: foto, nome (link para a ficha) e partido. */
function cabecaDeCandidato(c: CandidatoRef, lado: "nosso" | "ref"): HTMLTableCellElement {
  const a = h("a", { href: hashDaFicha(c), textContent: c.nm_urna });
  ligarMarca(a, tooltip(), () => cartao(c));
  const th = h("th", { scope: "col", className: `col-${lado}` },
    figuraCandidato(c.nm_urna, c.foto_url, 40, 50), a, h("span", { className: "nota", textContent: `${c.partido.sigla} · ${c.sg_uf}` }));
  // Selo textual (nunca só cor): a conta publicada pode estar incompleta, e os R$/voto dependem dela.
  if (c.alerta_declaracao === true) th.append(h("span", { className: "selo-alerta", textContent: "possível declaração incompleta" }));
  return th;
}

function celulaDom(x: Celula, rotulo: string, lado: string, motivoPadrao: string): HTMLTableCellElement {
  const td = h("td", { className: `${lado}${x.semDado ? " sem-dado" : ""}` });
  td.dataset["rotulo"] = rotulo;
  const span = h("span", { textContent: x.texto });
  if (x.semDado) {
    // Foco por teclado e balão com o motivo: "sem dado" nunca fica sem explicação.
    const motivo = x.motivo === "" ? motivoPadrao : x.motivo;
    span.tabIndex = 0;
    span.setAttribute("aria-label", `sem dado: ${motivo}`);
    ligarMarca(span, tooltip(), () => corpoRico({ titulo: "Sem dado", linhas: [["Motivo", motivo]] }));
  }
  td.append(span);
  return td;
}

function tabela(r: RespostaReferencias, nosso: CandidatoRef | null, ctx: Contexto): HTMLElement {
  const refs = r.referencia.candidatos;
  const nRef = refs.length;
  const medianaRotulo = `Mediana dos ${String(nRef)}`;
  const linhas = linhasDaTabela(refs, r.referencia.mediana, nosso);
  const t = h("table", { className: "tabela-comparar" });
  t.createCaption().textContent = `${r.nossos.rotulo} ao lado de ${r.referencia.rotulo}`;
  const cab = t.createTHead().insertRow();
  cab.append(h("th", { scope: "col", textContent: "Indicador" }), ...refs.map((c) => cabecaDeCandidato(c, "ref")), h("th", { scope: "col", className: "col-mediana", textContent: medianaRotulo }));
  if (nosso) cab.append(cabecaDeCandidato(nosso, "nosso"));
  const corpo = t.createTBody();
  for (const l of linhas) {
    const tr = corpo.insertRow();
    if (l.contexto) tr.className = "linha-contexto";
    const th = h("th", { scope: "row" }, l.rotulo, l.contexto ? h("span", { className: "nota", textContent: " (contexto)" }) : "", " ", ajuda(l.texto, ctx));
    tr.append(th);
    l.referencia.forEach((x, i) => { tr.append(celulaDom(x, refs[i]?.nm_urna ?? "Referência", "ref", "Este candidato não tem o dado publicado.")); });
    tr.append(celulaDom(l.mediana, medianaRotulo, "mediana", textoReferencia("sem_mediana")));
    if (l.nosso) tr.append(celulaDom(l.nosso, nosso?.nm_urna ?? "Nosso", "nosso", "Este candidato não tem o dado publicado."));
  }
  return h("div", { className: "tabela-comparar-rolagem" }, t);
}

export const tela: Tela = {
  titulo: "Comparar com outros partidos",
  render(container, { filtros }) {
    let bloco: BlocoId = blocoInicial(filtros.cargo);
    let uf = ufInicial(filtros.uf);
    let escolhido: number | null = null;
    const cliente = criarCliente();
    const seletor = h("div", { className: "comparar-seletor" });
    const conteudo = h("div");
    container.replaceChildren(titulo("Comparar com outros partidos"), cabecalhoDaTela("comparar"), seletor, conteudo);
    let parar: () => void = () => undefined;

    const trocar = (novoBloco: BlocoId, novaUf: string): void => {
      bloco = novoBloco; uf = novaUf; escolhido = null;
      desenharSeletor();
      parar();
      parar = carregar(conteudo, () => buscar(cliente, paramsReferencias(bloco, uf, null)), vazio, desenhar);
    };

    function desenharSeletor(): void {
      const grupo = h("div", { className: "bloco-grupo", role: "group" });
      grupo.setAttribute("aria-label", "O que comparar");
      for (const b of BLOCOS) {
        const botao = h("button", { type: "button", className: "bloco-botao", textContent: b.titulo });
        botao.setAttribute("aria-pressed", String(b.id === bloco));
        botao.addEventListener("click", () => { if (b.id !== bloco) trocar(b.id, uf); });
        grupo.append(botao);
      }
      const atual = BLOCOS.find((b) => b.id === bloco);
      const campoUf = atual?.comUf ? [campoSelect("UF", "uf-comparar", UFS.map((u) => ({ valor: u, texto: u })), uf, (v) => { trocar(bloco, v); }).rotulo] : [];
      seletor.replaceChildren(grupo, ...campoUf);
    }

    function vazio(c: Carga): string | null {
      if (c.tipo === "indisponivel") return c.mensagem;
      const { referencia, nossos } = c.dados;
      if (referencia.candidatos.length === 0) return referencia.motivo_vazio ?? textoReferencia("sem_referencia", { uf });
      if (nossos.candidatos.length === 0) return nossos.motivo_vazio ?? "O Partido Missão não tem candidatos neste cargo e UF.";
      return null;
    }

    function desenhar(c: Carga, destino: HTMLElement): (() => void) | undefined {
      if (c.tipo !== "ok") return undefined;
      const r = c.dados;
      const todos = r.nossos.candidatos;
      const ctx: Contexto & { contas_parciais: boolean; referencia_presidente: boolean } = {
        dt_geracao: r.dt_geracao, mes_base_ipca: r.base_ipca ?? undefined, contas_parciais: r.contas_parciais, referencia_presidente: bloco === "presidente",
      };
      const primeiro = escolherNosso(todos);
      const nosso = (): CandidatoRef | null => todos.find((x) => x.sq_candidato === escolhido) ?? primeiro;
      const textos = blocoReferencia(bloco, { uf, nome: primeiro?.nm_urna ?? "O candidato" });
      let grafico: ReturnType<typeof renderIndice> | null = null;

      const areaTabela = h("div");
      const areaGrafico = h("div", { className: "grafico-indice" });
      const desenharResultado = (): void => {
        const n = nosso();
        areaTabela.replaceChildren(tabela(r, n, ctx));
        grafico?.destruir(); grafico = null;
        areaGrafico.replaceChildren();
        const pontos = pontosDeIndice(n);
        if (n === null || pontos.length === 0) { areaGrafico.append(nota(textoReferencia("sem_mediana"))); return; }
        grafico = renderIndice(areaGrafico, pontos, { titulo: `${n.nm_urna} em vezes a mediana dos ${String(r.referencia.candidatos.length)} de referência`, nome: n.nm_urna });
      };

      // ---- busca do nosso candidato (só quando há mais de um) ----
      const busca: Node[] = [];
      if (todos.length > 1) {
        const estado = h("p", { className: "nota" });
        estado.setAttribute("aria-live", "polite");
        const resultados = h("ul", { className: "busca-redes-resultados" });
        const campo = h("input", { type: "search", name: "busca-comparar", placeholder: "Nome do candidato do Missão", maxLength: 80, autocomplete: "off" });
        campo.addEventListener("input", () => {
          const achados = buscarNossos(todos, campo.value);
          resultados.replaceChildren(...achados.map((a) => {
            const b = h("button", { type: "button", textContent: a.nm_urna });
            b.append(h("span", { className: "nota", textContent: ` · ${formatarNumero(a.votos)} votos` }));
            b.addEventListener("click", () => { escolhido = a.sq_candidato; campo.value = a.nm_urna; resultados.replaceChildren(); estado.textContent = ""; desenharResultado(); });
            return h("li", {}, b);
          }));
          const q = campo.value.trim();
          estado.textContent = q.length < 2 ? "" : achados.length === 0 ? "Nenhum candidato do Missão com esse nome aqui." : `${String(achados.length)} ${achados.length === 1 ? "resultado" : "resultados"}.`;
        });
        busca.push(
          h("div", { className: "controles" }, h("label", {}, "Escolher o candidato do Missão", campo)),
          estado, resultados,
          nota(`Mostrando ${primeiro?.nm_urna ?? ""} por padrão (o mais votado do Missão). ${String(todos.length)} candidatos do Missão neste recorte.`),
        );
      }

      const fonte = fonteUi(r.fontes, r.fontes.map((f) => f.dataset));
      const aviso = avisosUi("comparar", ctx);
      const menos = r.referencia.candidatos.length < N_ESPERADO && bloco !== "presidente"
        ? [nota(textoReferencia("menos_de_cinco", { n: String(r.referencia.candidatos.length), uf }))] : [];

      destino.append(
        ...(aviso ? [aviso] : []),
        h("section", { className: "comparar-cabecalho" },
          h("h2", { textContent: r.rotulo }),
          h("p", { textContent: textos.quem }),
          h("p", { className: "lados" },
            h("span", { className: "lado lado-nosso", textContent: "■ Missão (nosso)" }), " ",
            h("span", { className: "lado lado-ref", textContent: "◆ Outros partidos (referência)" }), " ", ajuda("selecao_referencia", ctx), fonte),
          ...menos,
        ),
        ...busca,
        areaTabela,
        h("h2", {}, "Onde estamos em relação à mediana ", ajuda("perfil_relativo", ctx)),
        nota("1× é igual à mediana dos de referência. À esquerda da linha, abaixo dela; à direita, acima. Descrição, não julgamento: custo por voto menor, por exemplo, não é “melhor” sozinho."),
        areaGrafico,
        rodapeUi("comparar", ctx),
      );
      desenharResultado();
      return () => { grafico?.destruir(); };
    }

    desenharSeletor();
    parar = carregar(conteudo, () => buscar(cliente, paramsReferencias(bloco, uf, null)), vazio, desenhar);
    return () => { parar(); container.replaceChildren(); };
  },
};
