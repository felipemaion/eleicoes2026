import { escalaIgualNosDoisAnos, mapaDeDiferenca, paramsDeFiltros, paresDaComparacao } from "../dados/adaptadores";
import { criarCliente } from "../dados/cliente";
import { render as renderComparacao } from "../componentes/graficos/comparacao";
import { render as renderKpi } from "../componentes/graficos/kpi";
import type { MetaIndicador } from "../componentes/escalas/escalas";
import { formatarDecimal, formatarPercentual } from "../formato";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { montarMapa } from "./mapa-embutido";
import type { Tela } from "./tipos";

const META_PENETRACAO: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "% dos eleitores aptos", denominador: "eleitores aptos do município" };

function figura(legenda: string): { fig: HTMLElement; area: HTMLElement } {
  const area = h("div", { className: "mapa-area" });
  return { fig: h("figure", {}, h("figcaption", { textContent: legenda }), area), area };
}

export const tela: Tela = {
  titulo: "Evolução 2022×2026",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const conteudo = h("div");
    container.replaceChildren(titulo("Evolução 2022×2026"), conteudo);
    let comparacao = "";
    let parar = (): void => { /* ainda sem busca */ };

    const iniciar = (focar?: string): void => {
      parar();
      parar = carregar(
        conteudo,
        () => Promise.all([cliente.comparativo({ ...paramsDeFiltros(filtros), comparacao: comparacao || undefined }), cliente.grupos()]),
        ([c]) => (c.municipios.length === 0 ? "Sem dados comparáveis entre 2022 e 2026 para estes filtros." : null),
        ([c, g], destino) => {
          comparacao = comparacao || g.comparacoes[0]?.id || "";
          const seletor = campoSelect("Comparar", "comparacao", g.comparacoes.map((x) => ({ valor: x.id, texto: x.rotulo })), comparacao, (v) => { comparacao = v; iniciar("comparacao"); });
          const kpis = h("div");
          const kpi = renderKpi(kpis, [
            { rotulo: `Penetração ${c.rotulo_antes}`, valor: c.kpis.penetracao_antes, formato: "percentual", unidade: "% dos aptos" },
            { rotulo: `Penetração ${c.rotulo_depois}`, valor: c.kpis.penetracao_depois, formato: "percentual", unidade: "% dos aptos" },
            ...(c.kpis.retencao === null ? [] : [{ rotulo: "Retenção", valor: c.kpis.retencao, formato: "percentual" as const, unidade: "votos de 2026 que já eram do grupo em 2022 (razão)" }]),
          ]);
          const a = figura(c.rotulo_antes);
          const d = figura(c.rotulo_depois);
          const dif = figura("Diferença (Δ penetração por AMC)");
          const areaComp = h("div");
          const comp = renderComparacao(areaComp, paresDaComparacao(c), { titulo: "Penetração por candidato", rotuloAntes: c.rotulo_antes, rotuloDepois: c.rotulo_depois, formato: formatarPercentual });
          destino.append(
            h("div", { className: "controles" }, seletor.rotulo), kpis,
            h("h2", { textContent: "Mapas lado a lado" }),
            h("div", { className: "mapas-3" }, a.fig, d.fig, dif.fig),
            nota("Os mapas de 2022 e 2026 usam as mesmas quebras de cor. Zonas eleitorais não são comparadas entre anos (rezoneamento); a comparação é por município agregado (AMC)."),
            h("h2", { textContent: "Comparação por candidato (mesmos candidatos nos dois anos)" }), areaComp,
            nota(`Retenção: ${c.kpis.retencao === null ? "indisponível" : formatarDecimal(c.kpis.retencao)}. Valores monetários de 2022 deflacionados para ${c.mes_base_deflator}.`),
          );
          if (focar) destino.querySelector<HTMLElement>(`[name=${focar}]`)?.focus();

          let vivo = true;
          const nomes = new Map(c.municipios.map((m) => [m.cd_mun_ibge, m.nome]));
          const detalhes = (valores: Readonly<Record<string, number>>): Record<string, { nome: string; taxa: number }> =>
            Object.fromEntries(Object.entries(valores).map(([id, taxa]) => [id, { nome: nomes.get(id) ?? id, taxa }]));
          const escalas = escalaIgualNosDoisAnos(c.penetracao_antes, c.penetracao_depois);
          const diff = mapaDeDiferenca(c);
          const montagens = [
            montarMapa(a.area, `Mapa de penetração, ${c.rotulo_antes}`).then((m) => { if (vivo) m.definirValores(c.penetracao_antes, escalas.antes, META_PENETRACAO, detalhes(c.penetracao_antes)); return m; }),
            montarMapa(d.area, `Mapa de penetração, ${c.rotulo_depois}`).then((m) => { if (vivo) m.definirValores(c.penetracao_depois, escalas.depois, META_PENETRACAO, detalhes(c.penetracao_depois)); return m; }),
            montarMapa(dif.area, "Mapa da diferença de penetração").then((m) => { if (vivo) m.definirValores(diff.valores, diff.escala, diff.meta, diff.detalhes); return m; }),
          ];
          Promise.all(montagens).catch((e: unknown) => { if (vivo) destino.append(h("p", { role: "alert", textContent: `Não foi possível desenhar os mapas: ${e instanceof Error ? e.message : String(e)}` })); });
          return () => {
            vivo = false;
            kpi.destruir();
            comp.destruir();
            for (const p of montagens) void p.then((m) => { m.destruir(); }, () => { /* nunca montou */ });
          };
        },
      );
    };
    iniciar();
    return () => { parar(); container.replaceChildren(); };
  },
};
