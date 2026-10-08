import { paramsDeFiltros } from "../dados/adaptadores";
import { criarCliente } from "../dados/cliente";
import type { Candidato, RespostaMapa, RespostaMunicipio } from "../dados/contrato";
import { formatarInteiro, formatarPercentual } from "../formato";
import { campoSelect, h, nota, titulo } from "./dom";
import { mostrarErro } from "./estados";
import { criarPainelMapa, UF_COM_GEOMETRIA } from "./painel-mapa";
import type { Tela } from "./tipos";

const INDICADORES = [
  { valor: "penetracao", texto: "Penetração (% dos aptos)" },
  { valor: "pct_validos", texto: "% dos votos válidos" },
  { valor: "lq", texto: "Quociente locacional (LQ)" },
  { valor: "swing", texto: "Swing 2022→2026" },
] as const;

function desenharMunicipio(destino: HTMLElement, m: RespostaMunicipio): void {
  destino.replaceChildren(
    h("h2", { textContent: `${m.nome} (${m.uf})` }),
    h("p", { textContent: `Eleitores aptos: ${formatarInteiro(m.aptos)}` }),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", { textContent: "Grupo", scope: "col" }), h("th", { textContent: "Votos", scope: "col" }), h("th", { textContent: "% dos aptos", scope: "col" }))),
      h("tbody", {}, ...m.grupos.map((g) => h("tr", {}, h("th", { textContent: g.rotulo, scope: "row" }), h("td", { textContent: formatarInteiro(g.votos) }), h("td", { textContent: formatarPercentual(g.taxa) }))))),
  );
}

export const tela: Tela = {
  titulo: "Mapa",
  render(container, { filtros }) {
    const cliente = criarCliente();
    let indicador = "penetracao";
    let candidato = "";
    let densidade = true;
    let vivo = true;

    const status = h("div", { className: "estado" });
    const area = h("div", { className: "mapa-area" });
    const painel = h("aside", { className: "painel-municipio" });
    painel.setAttribute("aria-live", "polite");
    painel.append(h("p", { textContent: "Escolha um município para ver o resumo." }));

    const nivel = campoSelect("Nível", "nivel", [
      { valor: "municipio", texto: "Município" },
      { valor: "zona", texto: "Zona eleitoral (em breve)", desabilitada: true },
      { valor: "h3", texto: "Hexágono H3 (em breve)", desabilitada: true },
    ], "municipio", () => { /* só município até os PMTiles (T-D04) */ });
    const ind = campoSelect("Indicador", "indicador", INDICADORES, indicador, (v) => { indicador = v; void atualizar(); });
    const cand = campoSelect("Candidato", "candidatoMapa", [{ valor: "", texto: "Grupo inteiro" }], "", (v) => { candidato = v; void atualizar(); });
    const mun = campoSelect("Resumo do município", "municipio", [{ valor: "", texto: "Selecione…" }], "", (v) => {
      if (v === "") return;
      cliente.municipio(v).then((m) => { if (vivo) desenharMunicipio(painel, m); }, (e: unknown) => { if (vivo) mostrarErro(painel, e, () => { mun.select.dispatchEvent(new Event("change")); }); });
    });
    const dens = h("input", { type: "checkbox", name: "densidade", checked: densidade });
    dens.addEventListener("change", () => { densidade = dens.checked; void pontos(); });

    const avisoGeo = filtros.uf === UF_COM_GEOMETRIA
      ? null
      : nota(`Geometria de demonstração: enquanto os PMTiles do Brasil não existem, o mapa desenha apenas Sergipe (UF selecionada: ${filtros.uf}).`);
    container.replaceChildren(
      titulo("Mapa"),
      ...(avisoGeo ? [avisoGeo] : []),
      h("div", { className: "controles" }, ind.rotulo, nivel.rotulo, cand.rotulo, mun.rotulo, h("label", {}, dens, " Densidade de votos (locais)")),
      status,
      h("div", { className: "mapa-layout" }, area, painel),
    );

    const mapa = criarPainelMapa(area, cliente, `Mapa de ${filtros.uf === "BR" ? "municípios" : `municípios — ${filtros.uf}`}`);
    const parametros = (): Record<string, string | undefined> => ({
      ...paramsDeFiltros(filtros), indicador, nivel: "municipio", sq_candidato: candidato || undefined,
    });

    function preencherMunicipios(r: RespostaMapa): void {
      const atual = mun.select.value;
      const ordenados = Object.entries(r.detalhes).map(([id, d]) => ({ id, nome: d.nome ?? id })).sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
      mun.select.replaceChildren(new Option("Selecione…", ""), ...ordenados.map((o) => new Option(o.nome, o.id)));
      mun.select.value = atual;
    }

    async function pontos(): Promise<void> {
      try {
        await mapa.mostrarPontos(densidade ? parametros() : null);
      } catch (e) {
        if (vivo) mostrarErro(status, e, () => { void pontos(); });
      }
    }

    async function atualizar(): Promise<void> {
      status.replaceChildren(h("p", { textContent: "Carregando…" }));
      status.firstElementChild?.setAttribute("role", "status");
      try {
        const r = await mapa.atualizar(parametros());
        if (!vivo || r === null) return;
        preencherMunicipios(r);
        status.replaceChildren();
        await pontos();
      } catch (e) {
        if (vivo) mostrarErro(status, e, () => { void atualizar(); });
      }
    }

    cliente.candidatos(paramsDeFiltros(filtros)).then((r) => {
      if (!vivo) return;
      const unicos: Candidato[] = r.candidatos;
      cand.select.append(...unicos.map((c) => new Option(c.nome, c.sq_candidato)));
    }, () => { /* a lista é opcional; o mapa do grupo funciona sem ela */ });

    void atualizar();
    return () => { vivo = false; mapa.destruir(); container.replaceChildren(); };
  },
};
