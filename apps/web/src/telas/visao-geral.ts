import { criarCliente } from "../dados/cliente";
import { kpisDoGrupo, paramsDeFiltros, rankingDeCandidatos } from "../dados/adaptadores";
import { render as renderKpi } from "../componentes/graficos/kpi";
import { render as renderRanking } from "../componentes/graficos/ranking";
import { formatarNumero } from "../formato";
import { h, titulo } from "./dom";
import { carregar } from "./estados";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

export const tela: Tela = {
  titulo: "Visão geral",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const conteudo = h("div");
    container.replaceChildren(titulo("Visão geral"), cabecalhoDaTela("visao-geral"), conteudo);
    let parar = (): void => { /* ainda sem busca */ };

    const iniciar = (): void => {
      parar();
      parar = carregar(
        conteudo,
        () => {
          const p = paramsDeFiltros(filtros);
          // 500 é o teto da API: a soma dos KPIs só é completa se `total` couber nele.
          return Promise.all([cliente.candidatos({ ...p, limite: "500" }), cliente.gastos(p)]);
        },
        ([r]) => (r.itens.length === 0 ? "Nenhum candidato encontrado para estes filtros." : null),
        ([r, g], destino) => {
          const kpis = h("div");
          const ranking = h("div");
          const ctx = { dt_geracao: g.dt_geracao, mes_base_ipca: g.base_ipca ?? undefined, contas_parciais: g.contas_parciais };
          const kpiHandle = renderKpi(kpis, kpisDoGrupo(r, g), { ajuda: (k) => ajuda(k, ctx) });
          const rk = renderRanking(ranking, rankingDeCandidatos(r.itens), { titulo: "Votos por candidato", formato: formatarNumero, colunaValor: "Votos" });
          destino.append(...[avisosUi("visao-geral", ctx)].filter((x) => x !== null), kpis, h("h2", { textContent: "Ranking de candidatos" }), ranking, rodapeUi("visao-geral", ctx));
          return () => { kpiHandle.destruir(); rk.destruir(); };
        },
      );
    };
    iniciar();
    return () => { parar(); container.replaceChildren(); };
  },
};
