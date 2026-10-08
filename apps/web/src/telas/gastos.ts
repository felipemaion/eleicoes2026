import { criarCliente } from "../dados/cliente";
import { avisosGastos, dispersaoCustoVoto, paramsDeFiltros, receitaEmpilhada } from "../dados/adaptadores";
import { render as renderDispersao } from "../componentes/graficos/dispersao";
import { render as renderEmpilhado } from "../componentes/graficos/empilhado";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import type { Tela } from "./tipos";

export const tela: Tela = {
  titulo: "Gastos",
  render(container, { filtros }) {
    const conteudo = h("div");
    container.replaceChildren(titulo("Gastos"), conteudo);
    const parar = carregar(
      conteudo,
      () => criarCliente().gastos(paramsDeFiltros(filtros)),
      (g) => (g.candidatos.length === 0 ? "Sem gastos declarados para estes filtros." : null),
      (g, destino) => {
        let base: "contratado" | "pago" = "contratado";
        const kpis: Kpi[] = [];
        if (g.custo_voto_contratado !== null) kpis.push({ rotulo: "Custo por voto contratado", valor: g.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos" });
        if (g.custo_voto_pago !== null) kpis.push({ rotulo: "Custo por voto pago", valor: g.custo_voto_pago, formato: "moeda", unidade: "R$ pagos ÷ votos" });
        kpis.push(
          { rotulo: "% recursos públicos", valor: g.pct_publico, formato: "percentual", unidade: "FEFC + Fundo Partidário ÷ receitas" },
          { rotulo: "% autofinanciamento", valor: g.pct_autofinanciamento, formato: "percentual", unidade: "recursos próprios ÷ receitas" },
        );
        const avisos = h("ul", { className: "avisos" }, ...avisosGastos(g).map((a) => h("li", { textContent: a })));
        avisos.setAttribute("role", "note");
        const areaKpi = h("div");
        const areaDispersao = h("div");
        const areaReceita = h("div");
        const k = renderKpi(areaKpi, kpis);
        const d = renderDispersao(areaDispersao, dispersaoCustoVoto(g, base), { titulo: "Custo de campanha × votos por candidato" });
        const e = renderEmpilhado(areaReceita, receitaEmpilhada(g), { titulo: "Receita por fonte" });
        const seletor = campoSelect("Base do custo", "base", [{ valor: "contratado", texto: "Contratado" }, { valor: "pago", texto: "Pago" }], base, (v) => {
          base = v === "pago" ? "pago" : "contratado";
          d.atualizar(dispersaoCustoVoto(g, base));
        });
        destino.append(
          avisos, h("div", { className: "controles" }, seletor.rotulo), areaKpi,
          h("h2", { textContent: "Custo × votos" }), areaDispersao,
          nota("Escala logarítmica nos dois eixos; candidatos com custo ou votos zero ficam na faixa “0”. Custo por voto não é mostrado em mapa."),
          h("h2", { textContent: "Receita por fonte" }), areaReceita,
        );
        return () => { k.destruir(); d.destruir(); e.destruir(); };
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
