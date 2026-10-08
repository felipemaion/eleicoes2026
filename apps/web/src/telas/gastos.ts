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
      (g) => (g.por_candidato.length === 0 ? "Sem gastos declarados para estes filtros." : null),
      (g, destino) => {
        let base: "contratado" | "pago" = "contratado";
        const kpis: Kpi[] = [];
        const { agregado: ag, receitas: rc } = g;
        if (ag.custo_voto_contratado !== null) kpis.push({ rotulo: "Custo por voto contratado", valor: ag.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos" });
        if (ag.custo_voto_pago !== null) kpis.push({ rotulo: "Custo por voto pago", valor: ag.custo_voto_pago, formato: "moeda", unidade: "R$ pagos ÷ votos" });
        if (rc.pct_publico !== null) kpis.push({ rotulo: "% recursos públicos", valor: rc.pct_publico, formato: "pontos", unidade: "FEFC + Fundo Partidário ÷ receitas" });
        if (rc.pct_autofinanciamento !== null) kpis.push({ rotulo: "% autofinanciamento", valor: rc.pct_autofinanciamento, formato: "pontos", unidade: "recursos próprios ÷ receitas" });
        const avisos = h("aside", { className: "avisos" }, ...avisosGastos(g).map((a) => h("p", { textContent: a })));
        avisos.setAttribute("aria-label", "Avisos de leitura");
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
