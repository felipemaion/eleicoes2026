import { criarCliente } from "../dados/cliente";
import { kpisDoGrupo, paramsDeFiltros, rankingDeCandidatos } from "../dados/adaptadores";
import { render as renderKpi } from "../componentes/graficos/kpi";
import { render as renderRanking } from "../componentes/graficos/ranking";
import { formatarNumero } from "../formato";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import type { Tela } from "./tipos";

export const tela: Tela = {
  titulo: "Visão geral",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const conteudo = h("div");
    container.replaceChildren(titulo("Visão geral"), conteudo);
    let comparacao = "";
    let soIndicados = false;
    let parar = (): void => { /* ainda sem busca */ };

    const iniciar = (focar?: string): void => {
      parar();
      parar = carregar(
        conteudo,
        () => Promise.all([cliente.candidatos({ ...paramsDeFiltros(filtros), comparacao: comparacao || undefined }), cliente.grupos()]),
        ([r]) => (r.candidatos.length === 0 ? "Nenhum candidato encontrado para estes filtros." : null),
        ([r, g], destino) => {
          comparacao = comparacao || g.comparacoes[0]?.id || "";
          const seletor = campoSelect("Comparar", "comparacao", g.comparacoes.map((c) => ({ valor: c.id, texto: c.rotulo })), comparacao, (v) => { comparacao = v; iniciar("comparacao"); });
          const caixa = h("input", { type: "checkbox", name: "so-indicados", checked: soIndicados });
          const rotuloCaixa = h("label", {}, caixa, " Só candidatos indicados pelo grupo");
          const kpis = h("div");
          const ranking = h("div");
          const kpiHandle = r.kpis ? renderKpi(kpis, kpisDoGrupo(r.kpis)) : null;
          const barras = (): ReturnType<typeof rankingDeCandidatos> => rankingDeCandidatos(r.candidatos, soIndicados);
          const rk = renderRanking(ranking, barras(), { titulo: "Votos por candidato", formato: formatarNumero, colunaValor: "Votos" });
          caixa.addEventListener("change", () => { soIndicados = caixa.checked; rk.atualizar(barras()); });
          const avisos = [
            r.contas_parciais ? "Contas de 2026 parciais: custo por voto e receitas ainda mudam." : "",
            `Fonte: TSE. dt_geracao: ${r.dt_geracao ?? "indisponível"}.`,
          ].filter(Boolean);
          destino.append(
            h("div", { className: "controles" }, seletor.rotulo, rotuloCaixa),
            kpis,
            h("h2", { textContent: "Ranking de candidatos" }),
            ranking,
            ...avisos.map(nota),
          );
          if (focar) destino.querySelector<HTMLElement>(`[name=${focar}]`)?.focus();
          return () => { kpiHandle?.destruir(); rk.destruir(); };
        },
      );
    };
    iniciar();
    return () => { parar(); container.replaceChildren(); };
  },
};
