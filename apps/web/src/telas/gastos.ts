import { criarCliente, ErroApi, type ClienteApi } from "../dados/cliente";
import { cargoDaApi, paramsDeFiltros, receitaEmpilhada } from "../dados/adaptadores";
import { paramsComparativo, parseLado, resolverLados } from "../dados/comparador-logica";
import type { RespostaComparativo, RespostaGastos } from "../dados/contrato";
import { idsQueCasam, medianaCustoVoto, pontosDeGastos } from "../dados/gastos-logica";
import { kpisDeReceita, linhasDoComparativoReceitas, notaFaixaReceita, pontosDeReceita } from "../dados/receitas-logica";
import { formatarMoeda } from "../formato";
import { formatarMesBase } from "../textos";
import { render as renderDispersao } from "../componentes/graficos/dispersao";
import { render as renderEmpilhado } from "../componentes/graficos/empilhado";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const DATASETS_CONTAS = ["prestacao_contas"];
type Contexto = Parameters<typeof ajuda>[1];

/** Despesas: KPIs do grupo (custo por voto) — as receitas têm a própria seção. */
function kpisDeDespesa(g: RespostaGastos): Kpi[] {
  const ag = g.agregado;
  const k: Kpi[] = [];
  if (ag.custo_voto_contratado !== null) k.push({ fonte: "contas", rotulo: "Custo por voto contratado", ajuda: "custo_por_voto", valor: ag.custo_voto_contratado, formato: "moeda", unidade: "R$ contratados ÷ votos" });
  if (ag.custo_voto_pago !== null) k.push({ fonte: "contas", rotulo: "Custo por voto pago", ajuda: "custo_por_voto", valor: ag.custo_voto_pago, formato: "moeda", unidade: "R$ pagos ÷ votos" });
  k.push({ fonte: "contas", rotulo: "Dívida de campanha", ajuda: "divida", valor: ag.divida, formato: "moeda", unidade: "contratado − pago" });
  return k;
}

/** `/comparativo` responde 422 sem candidaturas num dos lados: aqui isso só significa "sem comparação". */
async function comparativoDeReceitas(cliente: ClienteApi, filtros: Parameters<typeof paramsDeFiltros>[0]): Promise<RespostaComparativo | null> {
  const grupos = await cliente.grupos();
  const lados = resolverLados(parseLado(filtros.de), parseLado(filtros.para), grupos.comparacoes, filtros.grupo);
  try {
    return await cliente.comparativo(paramsComparativo(lados.de, lados.para, cargoDaApi(filtros.cargo), filtros.uf, grupos.comparacoes));
  } catch (e) {
    if (e instanceof ErroApi && e.status === 422) return null;
    throw e;
  }
}

function tabelaComparativo(c: RespostaComparativo, ctx: Contexto): HTMLElement {
  const r = c.receitas;
  if (r === null) return h("p", { className: "estado vazio", textContent: "Sem comparação de receitas: um dos lados não tem prestação de contas publicada." });
  const mes = formatarMesBase(r.base_ipca);
  const linhas = linhasDoComparativoReceitas(r);
  const tabela = h("table", { className: "tabela-comparativo-receitas" },
    h("caption", { textContent: `Receitas: ${c.rotulo}. Valores de 2022 corrigidos pelo IPCA para R$ de ${mes}.` }),
    h("thead", {}, h("tr", {}, ...["Indicador", `2022 (R$ de ${mes})`, "2022 como publicado", "2026", "Variação"].map((t) => h("th", { scope: "col", textContent: t })))),
    h("tbody", {}, ...linhas.map((l) => h("tr", {},
      h("th", { scope: "row" }, l.rotulo, " ", ajuda(l.ajuda, { ...ctx, mes_base_ipca: r.base_ipca })),
      h("td", { textContent: l.de }),
      h("td", { textContent: l.deNominal ?? "—" }),
      h("td", { textContent: l.para }),
      h("td", { textContent: l.variacao }),
    ))),
  );
  const rolagem = h("div", { className: "tabela-rolagem" }, tabela);
  rolagem.tabIndex = 0;
  rolagem.setAttribute("role", "region");
  rolagem.setAttribute("aria-label", "Tabela de receitas 2022 e 2026");
  return h("div", {}, rolagem, ...(r.contas_parciais_para ? [nota("As contas de 2026 ainda são parciais: queda de receita em relação a 2022 é esperada até a prestação final.")] : []));
}

export const tela: Tela = {
  titulo: "Financiamento",
  render(container, { filtros }) {
    const conteudo = h("div");
    container.replaceChildren(titulo("Financiamento"), cabecalhoDaTela("gastos"), conteudo);
    const cliente = criarCliente();
    const parar = carregar(
      conteudo,
      () => cliente.gastos(paramsDeFiltros(filtros)),
      (g) => (g.por_candidato.length === 0 ? "Sem receitas nem gastos declarados para estes filtros." : null),
      (g, destino) => {
        let base: "contratado" | "pago" = "contratado";
        const ctx = { dt_geracao: g.dt_geracao, mes_base_ipca: g.base_ipca ?? undefined, contas_parciais: g.contas_parciais };
        const kpiOpcoes = { ajuda: (k: string) => ajuda(k, ctx), fonte: () => fonteUi(g.fontes, DATASETS_CONTAS) };
        const areaKpiReceita = h("div");
        const areaKpiDespesa = h("div");
        const areaDispersaoReceita = h("div", { className: "grafico-receita" });
        const areaDispersaoDespesa = h("div", { className: "grafico-despesa" });
        const areaFonte = h("div");
        const areaComparativo = h("div");
        const kr = renderKpi(areaKpiReceita, kpisDeReceita(g), kpiOpcoes);
        const kd = renderKpi(areaKpiDespesa, kpisDeDespesa(g), kpiOpcoes);

        let consulta = "";
        const pontosDespesa = (): ReturnType<typeof pontosDeGastos> => pontosDeGastos(g, base);
        const pontosReceita = pontosDeReceita(g);
        const montarDespesa = (): ReturnType<typeof renderDispersao> => {
          const m = medianaCustoVoto(pontosDespesa());
          const ref = m === null ? {} : { referencia: { custoPorVoto: m, rotulo: `mediana ${formatarMoeda(m)} por voto (${base})` } };
          return renderDispersao(areaDispersaoDespesa, pontosDespesa(), { titulo: "Custo de campanha × votos por candidato", destaque: idsQueCasam(pontosDespesa(), consulta), ...ref });
        };
        const montarReceita = (): ReturnType<typeof renderDispersao> => {
          const m = g.receita_por_voto.mediana_receita_por_voto;
          const ref = m === null ? {} : { referencia: { custoPorVoto: m, rotulo: `mediana ${formatarMoeda(m)} de receita por voto` } };
          return renderDispersao(areaDispersaoReceita, pontosReceita, { titulo: "Receita de campanha × votos por candidato", grandeza: "receita de campanha", destaque: idsQueCasam(pontosReceita, consulta), ...ref });
        };
        let dd = montarDespesa();
        const dr = montarReceita();
        const e = renderEmpilhado(areaFonte, receitaEmpilhada(g), { titulo: "Receita por fonte" });
        const seletor = campoSelect("Base do custo", "base", [{ valor: "contratado", texto: "Contratado" }, { valor: "pago", texto: "Pago" }], base, (v) => {
          base = v === "pago" ? "pago" : "contratado";
          // A linha de referência muda com a base; o destaque da busca é reaplicado em `montarDespesa`.
          dd.destruir();
          dd = montarDespesa();
        });
        const estado = h("p", { className: "nota busca-gastos-estado" });
        estado.setAttribute("aria-live", "polite");
        const campo = h("input", { type: "search", name: "busca-gastos", placeholder: "Nome do candidato", maxLength: 80 });
        campo.addEventListener("input", () => {
          consulta = campo.value;
          const ids = new Set([...idsQueCasam(pontosDespesa(), consulta), ...idsQueCasam(pontosReceita, consulta)]);
          dd.destacar(idsQueCasam(pontosDespesa(), consulta));
          dr.destacar(idsQueCasam(pontosReceita, consulta));
          estado.textContent = consulta.trim() === "" ? "" : ids.size === 0 ? "Nenhum candidato com esse nome neste recorte." : `${String(ids.size)} ${ids.size === 1 ? "candidato realçado" : "candidatos realçados"} nos gráficos.`;
        });
        const busca = h("label", {}, "Realçar candidato nos gráficos", campo);
        const faixa = notaFaixaReceita(g);
        const semReceita = g.receitas === null;

        destino.append(
          ...[avisosUi("gastos", ctx)].filter((x) => x !== null),
          h("div", { className: "controles" }, seletor.rotulo, busca), estado,
          h("h2", {}, "Receitas ", fonteUi(g.fontes, DATASETS_CONTAS)),
          ...(semReceita ? [nota("Nenhum candidato do recorte tem receita declarada: sem prestação de contas, os indicadores de receita ficam indisponíveis (não são zero).")] : [areaKpiReceita]),
          ...(faixa ? [nota(faixa)] : []),
          ...(semReceita ? [] : [
            h("h3", {}, "Receita por fonte"), areaFonte,
            h("h3", {}, "Receita × votos"), areaDispersaoReceita,
            nota("Cada círculo é um candidato; clique para abrir a página dele no TSE. Escala logarítmica nos dois eixos; candidatos sem receita declarada não aparecem (sem linha de receita não é o mesmo que zero)."),
          ]),
          h("h2", {}, "Despesas e saldo ", fonteUi(g.fontes, DATASETS_CONTAS)),
          areaKpiDespesa,
          h("h3", {}, "Custo × votos"), areaDispersaoDespesa,
          nota("Passe o mouse (ou foque com Tab) sobre um círculo para ver o candidato. Escala logarítmica nos dois eixos; candidatos com custo ou votos zero ficam na faixa “0”. O saldo de cada candidato (receita − despesa contratada) está no balão do gráfico. Custo por voto não é mostrado em mapa."),
          h("h2", {}, "2022 × 2026, com 2022 corrigido pela inflação"), areaComparativo,
          rodapeUi("gastos", ctx),
        );

        // Comparação em paralelo: se falhar, só ela some — receitas e despesas já estão na tela.
        let ativo = true;
        areaComparativo.append(nota("Carregando comparação…"));
        comparativoDeReceitas(cliente, filtros).then(
          (c) => { if (ativo) areaComparativo.replaceChildren(c === null ? nota("Sem comparação: um dos lados não tem candidaturas neste cargo e UF.") : tabelaComparativo(c, ctx)); },
          (erro: unknown) => { console.error("Comparação de receitas indisponível:", erro); if (ativo) areaComparativo.replaceChildren(nota("Não foi possível carregar a comparação agora.")); },
        );
        return () => { ativo = false; kr.destruir(); kd.destruir(); dd.destruir(); dr.destruir(); e.destruir(); };
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
