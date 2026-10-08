import { criarCliente } from "../dados/cliente";
import { paramsDeFiltros, receitaEmpilhada } from "../dados/adaptadores";
import { idsQueCasam, medianaCustoVoto, pontosDeGastos } from "../dados/gastos-logica";
import { formatarMoeda } from "../formato";
import { render as renderDispersao } from "../componentes/graficos/dispersao";
import { render as renderEmpilhado } from "../componentes/graficos/empilhado";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

export const tela: Tela = {
  titulo: "Gastos",
  render(container, { filtros }) {
    const conteudo = h("div");
    container.replaceChildren(titulo("Gastos"), cabecalhoDaTela("gastos"), conteudo);
    const parar = carregar(
      conteudo,
      async () => {
        const cliente = criarCliente();
        const p = paramsDeFiltros(filtros);
        // Partido e resultado não vêm em /gastos: a lista de candidatos do mesmo recorte completa o tooltip.
        const [g, c] = await Promise.all([cliente.gastos(p), cliente.candidatos({ ...p, limite: "500" })]);
        return { g, candidatos: c.itens };
      },
      ({ g }) => (g.por_candidato.length === 0 ? "Sem gastos declarados para estes filtros." : null),
      ({ g, candidatos }, destino) => {
        let base: "contratado" | "pago" = "contratado";
        const kpis: Kpi[] = [];
        const { agregado: ag, receitas: rc } = g;
        if (ag.custo_voto_contratado !== null) kpis.push({ fonte: "contas", rotulo: "Custo por voto contratado", ajuda: "custo_por_voto", valor: ag.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos" });
        if (ag.custo_voto_pago !== null) kpis.push({ fonte: "contas", rotulo: "Custo por voto pago", ajuda: "custo_por_voto", valor: ag.custo_voto_pago, formato: "moeda", unidade: "R$ pagos ÷ votos" });
        if (rc.pct_publico !== null) kpis.push({ fonte: "contas", rotulo: "% recursos públicos", ajuda: "pct_publico", valor: rc.pct_publico, formato: "pontos", unidade: "FEFC + Fundo Partidário ÷ receitas" });
        if (rc.pct_autofinanciamento !== null) kpis.push({ fonte: "contas", rotulo: "% autofinanciamento", ajuda: "pct_autofinanciamento", valor: rc.pct_autofinanciamento, formato: "pontos", unidade: "recursos próprios ÷ receitas" });
        const ctx = { dt_geracao: g.dt_geracao, mes_base_ipca: g.base_ipca ?? undefined, contas_parciais: g.contas_parciais };
        const areaKpi = h("div");
        const areaDispersao = h("div");
        const areaReceita = h("div");
        const k = renderKpi(areaKpi, kpis, { ajuda: (k) => ajuda(k, ctx), fonte: () => fonteUi(g.fontes, ["prestacao_contas"]) });
        let consulta = "";
        const pontos = (): ReturnType<typeof pontosDeGastos> => pontosDeGastos(g, candidatos, base);
        const referencia = (): { custoPorVoto: number; rotulo: string } | undefined => {
          const m = medianaCustoVoto(pontos());
          return m === null ? undefined : { custoPorVoto: m, rotulo: `mediana ${formatarMoeda(m)} por voto (${base})` };
        };
        const montar = (): ReturnType<typeof renderDispersao> => {
          const ref = referencia();
          return renderDispersao(areaDispersao, pontos(), { titulo: "Custo de campanha × votos por candidato", destaque: idsQueCasam(pontos(), consulta), ...(ref ? { referencia: ref } : {}) });
        };
        let d = montar();
        const e = renderEmpilhado(areaReceita, receitaEmpilhada(g), { titulo: "Receita por fonte" });
        const seletor = campoSelect("Base do custo", "base", [{ valor: "contratado", texto: "Contratado" }, { valor: "pago", texto: "Pago" }], base, (v) => {
          base = v === "pago" ? "pago" : "contratado";
          // A linha de referência muda com a base; o destaque da busca é reaplicado em `montar`.
          d.destruir();
          d = montar();
        });
        const estado = h("p", { className: "nota busca-gastos-estado" });
        estado.setAttribute("aria-live", "polite");
        const campo = h("input", { type: "search", name: "busca-gastos", placeholder: "Nome do candidato", maxLength: 80 });
        campo.addEventListener("input", () => {
          consulta = campo.value;
          const ids = idsQueCasam(pontos(), consulta);
          d.destacar(ids);
          estado.textContent = consulta.trim() === "" ? "" : ids.size === 0 ? "Nenhum candidato com esse nome neste recorte." : `${String(ids.size)} ${ids.size === 1 ? "candidato realçado" : "candidatos realçados"} no gráfico.`;
        });
        const busca = h("label", {}, "Realçar candidato no gráfico", campo);
        destino.append(
          ...[avisosUi("gastos", ctx)].filter((x) => x !== null), h("div", { className: "controles" }, seletor.rotulo, busca), estado, areaKpi,
          h("h2", { textContent: "Custo × votos" }), areaDispersao,
          nota("Passe o mouse (ou foque com Tab) sobre um círculo para ver o candidato. Escala logarítmica nos dois eixos; candidatos com custo ou votos zero ficam na faixa “0”. Custo por voto não é mostrado em mapa."),
          h("h2", {}, "Receita por fonte ", fonteUi(g.fontes, ["prestacao_contas"])), areaReceita,
          rodapeUi("gastos", ctx),
        );
        return () => { k.destruir(); d.destruir(); e.destruir(); };
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
