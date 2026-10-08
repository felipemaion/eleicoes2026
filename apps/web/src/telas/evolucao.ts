import { escalaIgualNosDoisAnos, mapaDeDiferenca, paramsComCargo, penetracaoDosAnos } from "../dados/adaptadores";
import { criarCliente } from "../dados/cliente";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import type { MetaIndicador } from "../componentes/escalas/escalas";
import { formatarPermil } from "../formato";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { montarMapa } from "./mapa-embutido";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const META_PENETRACAO: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "‰", denominador: "eleitores aptos do município" };

function figura(legenda: string): { fig: HTMLElement; area: HTMLElement } {
  const area = h("div", { className: "mapa-area" });
  return { fig: h("figure", {}, h("figcaption", { textContent: legenda }), area), area };
}

export const tela: Tela = {
  titulo: "Evolução 2022×2026",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const conteudo = h("div");
    container.replaceChildren(titulo("Evolução 2022×2026"), cabecalhoDaTela("evolucao"), conteudo);
    let comparacao = "";
    let parar = (): void => { /* ainda sem busca */ };

    const iniciar = (focar?: string): void => {
      parar();
      parar = carregar(
        conteudo,
        async () => {
          // `comparacao` é obrigatória na API: sem escolha do usuário, usa a primeira comparação declarada.
          const g = await cliente.grupos();
          comparacao = comparacao || g.comparacoes[0]?.id || "";
          const c = await cliente.comparativo({ ...paramsComCargo(filtros), comparacao: comparacao || undefined });
          return [c, g] as const;
        },
        ([c]) => (c.municipios.length === 0 ? "Sem dados comparáveis entre 2022 e 2026 para estes filtros." : null),
        ([c, g], destino) => {
          comparacao = comparacao || g.comparacoes[0]?.id || "";
          const seletor = campoSelect("Comparar", "comparacao", g.comparacoes.map((x) => ({ valor: x.id, texto: x.rotulo })), comparacao, (v) => { comparacao = v; iniciar("comparacao"); });
          const { de, para, kpis: k } = c;
          const itens: Kpi[] = [];
          if (k.penetracao_de !== null) itens.push({ rotulo: `Penetração ${de.rotulo}`, ajuda: "penetracao", valor: k.penetracao_de, formato: "permil", unidade: "votos por mil aptos" });
          if (k.penetracao_para !== null) itens.push({ rotulo: `Penetração ${para.rotulo}`, ajuda: "penetracao", valor: k.penetracao_para, formato: "permil", unidade: "votos por mil aptos" });
          if (k.delta_penetracao !== null) itens.push({ rotulo: "Δ penetração", ajuda: "evolucao", valor: k.delta_penetracao, formato: "permil", unidade: "‰ — métrica-âncora (depois − antes)" });
          if (k.swing_pp !== null) itens.push({ rotulo: "Swing (% válidos)", ajuda: "evolucao", valor: k.swing_pp, formato: "pontos", unidade: "pontos percentuais" });
          if (k.retencao !== null) itens.push({ rotulo: "Retenção", ajuda: "evolucao", valor: k.retencao, formato: "percentual", unidade: "votos depois ÷ votos antes (nos municípios comparáveis)" });
          if (k.ganho_absoluto !== null) itens.push({ rotulo: "Ganho absoluto", ajuda: "evolucao", valor: k.ganho_absoluto, formato: "inteiro", unidade: "votos a mais que antes" });
          const kpis = h("div");
          const ctx = { dt_geracao: c.dt_geracao };
          const kpi = renderKpi(kpis, itens, { ajuda: (k) => ajuda(k, ctx) });
          const a = figura(de.rotulo);
          const d = figura(para.rotulo);
          const dif = figura("Diferença (Δ penetração por AMC)");
          destino.append(
            ...[avisosUi("evolucao", ctx)].filter((x) => x !== null),
            h("div", { className: "controles" }, seletor.rotulo), kpis,
            h("h2", { textContent: "Mapas lado a lado" }),
            h("div", { className: "mapas-3" }, a.fig, d.fig, dif.fig),
            nota("Os mapas de 2022 e 2026 usam as mesmas quebras de cor. Zonas eleitorais não são comparadas entre anos (rezoneamento); a comparação é por município agregado (AMC)."),
            ...(c.mesmos_candidatos ? [nota("Comparação restrita aos candidatos que concorreram nos dois anos.")] : []),
            rodapeUi("evolucao", ctx),
          );
          if (focar) destino.querySelector<HTMLElement>(`[name=${focar}]`)?.focus();

          let vivo = true;
          const nomes = new Map(c.municipios.map((m) => [String(m.cd_amc), m.nome]));
          const detalhes = (valores: Readonly<Record<string, number>>): Record<string, { nome: string; taxa: number }> =>
            Object.fromEntries(Object.entries(valores).map(([id, taxa]) => [id, { nome: nomes.get(id) ?? id, taxa }]));
          const pen = penetracaoDosAnos(c);
          const escalas = escalaIgualNosDoisAnos(pen.antes, pen.depois);
          const diff = mapaDeDiferenca(c);
          const opcoes = { ano: para.ano, formatarTaxa: formatarPermil };
          const montagens = [
            montarMapa(a.area, `Mapa de penetração, ${de.rotulo}`, opcoes).then((m) => { if (vivo) m.definirValores(pen.antes, escalas.antes, META_PENETRACAO, detalhes(pen.antes)); return m; }),
            montarMapa(d.area, `Mapa de penetração, ${para.rotulo}`, opcoes).then((m) => { if (vivo) m.definirValores(pen.depois, escalas.depois, META_PENETRACAO, detalhes(pen.depois)); return m; }),
            montarMapa(dif.area, "Mapa da diferença de penetração", opcoes).then((m) => { if (vivo) m.definirValores(diff.valores, diff.escala, diff.meta, diff.detalhes); return m; }),
          ];
          Promise.all(montagens).catch((e: unknown) => { if (vivo) destino.append(h("p", { role: "alert", textContent: `Não foi possível desenhar os mapas: ${e instanceof Error ? e.message : String(e)}` })); });
          return () => {
            vivo = false;
            kpi.destruir();
            for (const p of montagens) void p.then((m) => { m.destruir(); }, () => { /* nunca montou */ });
          };
        },
      );
    };
    iniciar();
    return () => { parar(); container.replaceChildren(); };
  },
};
