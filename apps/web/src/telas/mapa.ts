import { CARGO_PADRAO, paramsComCargo, paramsDeFiltros } from "../dados/adaptadores";
import { criarCliente, foiCancelada } from "../dados/cliente";
import type { IndicadorApi, RespostaMapa } from "../dados/contrato";
import type { Nivel } from "../componentes/mapa/mapa";
import { campoSelect, h, nota, titulo } from "./dom";
import { mostrarErro } from "./estados";
import { geometria, niveisDisponiveis, UF_DA_DEMONSTRACAO } from "./mapa-embutido";
import { criarPainelMapa } from "./painel-mapa";
import { desenharMunicipio, focarPainel } from "./painel-municipio";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const INDICADORES: readonly { valor: IndicadorApi; texto: string }[] = [
  { valor: "penetracao", texto: "Penetração (‰ dos aptos)" },
  { valor: "pct_validos", texto: "% dos votos válidos" },
];

/** O município de uma chave do mapa: "2800308" (município) ou "2800308-12" (zona). */
export const municipioDaChave = (id: string): string => id.split("-")[0] ?? id;

export const tela: Tela = {
  titulo: "Mapa",
  render(container, { filtros }) {
    const cliente = criarCliente();
    let indicador: IndicadorApi = "penetracao";
    let candidato = "";
    let nivelAtual: Nivel = "municipio";
    let densidade = true;
    let vivo = true;
    let seqAtualizar = 0;
    let seqMun = 0;
    let ctrlMun: AbortController | null = null;

    const status = h("div", { className: "estado" });
    const rodape = h("div");
    const area = h("div", { className: "mapa-area" });
    const painel = h("aside", { className: "painel-municipio" });
    painel.setAttribute("aria-live", "polite");
    painel.setAttribute("aria-label", "Resumo do município");
    painel.append(h("p", { textContent: "Clique em um município (ou use as setas e Enter com o mapa em foco) para ver o resumo." }));

    function selecionar(id: string): void {
      const ibge = municipioDaChave(id);
      ctrlMun?.abort();
      const ctrl = (ctrlMun = new AbortController());
      const minha = ++seqMun;
      const atual = (): boolean => vivo && minha === seqMun;
      cliente.municipio(ibge, ctrl.signal).then(
        (m) => { if (atual()) { desenharMunicipio(painel, m); focarPainel(painel); } },
        (e: unknown) => { if (atual() && !foiCancelada(e)) mostrarErro(painel, e, () => { selecionar(id); }); },
      );
    }

    const nivel = campoSelect("Nível", "nivel", [
      { valor: "municipio", texto: "Município" },
      { valor: "zona", texto: "Zona eleitoral", desabilitada: true },
      { valor: "h3", texto: "Hexágono H3 (em breve)", desabilitada: true },
    ], "municipio", (v) => {
      nivelAtual = v === "zona" ? "zona" : "municipio";
      void mapa.definirNivel(nivelAtual).then(atualizar);
    });
    const ind = campoSelect("Indicador", "indicador", INDICADORES, indicador, (v) => { indicador = v === "pct_validos" ? "pct_validos" : "penetracao"; mostrarAjuda(); void atualizar(); });
    const ajudaInd = h("span");
    const mostrarAjuda = (): void => { ajudaInd.replaceChildren(ajuda(indicador, {})); };
    mostrarAjuda();
    const cand = campoSelect("Candidato", "candidatoMapa", [{ valor: "", texto: "Grupo inteiro" }], "", (v) => { candidato = v; void atualizar(); });
    const dens = h("input", { type: "checkbox", name: "densidade", checked: densidade });
    dens.addEventListener("change", () => { densidade = dens.checked; void pontos(); });

    const avisos = h("div");
    container.replaceChildren(
      titulo("Mapa"),
      cabecalhoDaTela("mapa"),
      avisos,
      h("div", { className: "controles" }, ind.rotulo, ajudaInd, nivel.rotulo, cand.rotulo, h("label", {}, dens, " Densidade de votos (locais)")),
      status,
      h("div", { className: "mapa-layout" }, area, painel),
      // Avisos longos ficam abaixo do mapa: o mapa é o conteúdo principal e não deve sair da primeira tela.
      ...[avisosUi("mapa", {})].filter((x) => x !== null),
      rodape,
    );

    if (filtros.cargo === "todos") avisos.append(nota(`O mapa exige um cargo: mostrando ${CARGO_PADRAO.replace(/_/g, " ")}. Escolha outro no filtro Cargo.`));
    // Avisos que dependem da geometria disponível e habilitam o nível zona.
    void Promise.all([geometria(), niveisDisponiveis(filtros.ano)]).then(([g, niveis]) => {
      if (!vivo) return;
      if (g === "demonstracao" && filtros.uf !== UF_DA_DEMONSTRACAO) {
        avisos.append(nota(`Geometria de demonstração: os PMTiles do Brasil ainda não foram publicados e o mapa desenha apenas Sergipe (UF selecionada: ${filtros.uf}).`));
      }
      const zona = nivel.select.querySelector<HTMLOptionElement>("option[value=zona]");
      if (zona && niveis.includes("zona")) {
        if (filtros.uf === "BR") zona.textContent = "Zona eleitoral (escolha uma UF)";
        else zona.disabled = false;
      }
    }, (e: unknown) => { if (vivo) mostrarErro(status, e, () => { window.location.reload(); }); });

    const mapa = criarPainelMapa(area, cliente, `Mapa de ${filtros.uf === "BR" ? "municípios" : `municípios — ${filtros.uf}`}`, { ano: filtros.ano, aoSelecionar: (id) => { selecionar(id); } });
    const parametros = (): Record<string, string | undefined> => ({
      ...paramsComCargo(filtros), indicador, nivel: nivelAtual, sq_candidato: candidato || undefined,
      // `grupo` e `sq_candidato` são exclusivos na API.
      ...(candidato ? { grupo: undefined } : {}),
    });

    async function pontos(): Promise<void> {
      try {
        // /mapa/pontos exige UF; no Brasil inteiro a densidade fica desligada, com aviso na tela.
        await mapa.mostrarPontos(densidade && filtros.uf !== "BR" ? parametros() : null);
      } catch (e) {
        // Cancelada = substituída por pedido mais novo; o erro "real" só vale se ainda for o atual.
        if (vivo && !foiCancelada(e)) mostrarErro(status, e, () => { void pontos(); });
      }
    }

    async function atualizar(): Promise<void> {
      const minha = ++seqAtualizar;
      status.replaceChildren(h("p", { textContent: "Carregando…" }));
      status.firstElementChild?.setAttribute("role", "status");
      try {
        const r: RespostaMapa | null = await mapa.atualizar(parametros());
        if (!vivo || r === null || minha !== seqAtualizar) return;
        rodape.replaceChildren(rodapeUi("mapa", { dt_geracao: r.dt_geracao }));
        status.replaceChildren(...(r.escala_sugerida.aviso ? [nota(r.escala_sugerida.aviso)] : []));
        await pontos();
      } catch (e) {
        if (vivo && minha === seqAtualizar && !foiCancelada(e)) mostrarErro(status, e, () => { void atualizar(); });
      }
    }

    cliente.candidatos({ ...paramsDeFiltros(filtros), limite: "500" }).then((r) => {
      if (!vivo) return;
      cand.select.append(...r.itens.map((c) => new Option(c.nm_urna, String(c.sq_candidato))));
    }, () => { /* a lista é opcional; o mapa do grupo funciona sem ela */ });

    void atualizar();
    return () => { vivo = false; ctrlMun?.abort(); mapa.destruir(); container.replaceChildren(); };
  },
};
