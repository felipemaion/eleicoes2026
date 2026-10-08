import { barrasMunicipios, paramsDeFiltros, paramsComCargo } from "../dados/adaptadores";
import { criarCliente } from "../dados/cliente";
import type { Ficha } from "../dados/contrato";
import { render as renderBarras } from "../componentes/graficos/barras";
import { render as renderEmpilhado } from "../componentes/graficos/empilhado";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { formatarNumero } from "../formato";
import { formatarHash } from "../rotas";
import { campoSelect, h, titulo } from "./dom";
import { carregar, mostrarErro } from "./estados";
import { criarPainelMapa } from "./painel-mapa";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

function desenharFicha(destino: HTMLElement, f: Ficha, filtros: Parameters<Tela["render"]>[1]["filtros"]): () => void {
  const c = f.candidato;
  const kpis: Kpi[] = [{ rotulo: "Votos", valor: c.votos, formato: "inteiro" }];
  if (c.pct_validos !== null) kpis.push({ rotulo: "% dos válidos", ajuda: "pct_validos", valor: c.pct_validos, formato: "pontos", unidade: "% dos votos válidos" });
  if (c.penetracao !== null) kpis.push({ rotulo: "Penetração", ajuda: "penetracao", valor: c.penetracao, formato: "permil", unidade: "votos por mil aptos" });
  if (f.gastos?.custo_voto_contratado != null) kpis.push({ rotulo: "Custo por voto contratado", ajuda: "custo_por_voto", valor: f.gastos.custo_voto_contratado, formato: "moeda" });
  if (f.gastos?.custo_voto_pago != null) kpis.push({ rotulo: "Custo por voto pago", ajuda: "custo_por_voto", valor: f.gastos.custo_voto_pago, formato: "moeda" });
  const aKpi = h("div");
  const aBarras = h("div");
  const aReceita = h("div");
  const aMapa = h("div", { className: "mapa-area" });
  const ctx = { dt_geracao: f.dt_geracao, mes_base_ipca: f.base_ipca ?? undefined, contas_parciais: f.contas_parciais };
  const k = renderKpi(aKpi, kpis, { ajuda: (chave) => ajuda(chave, ctx) });
  const b = renderBarras(aBarras, barrasMunicipios(f, 10), { titulo: "Municípios com mais votos", formato: formatarNumero, colunaValor: "Votos" });
  const e = renderEmpilhado(aReceita, f.receitas ? [{ rotulo: c.nm_urna, valores: f.receitas.por_categoria }] : [], { titulo: "Receita por fonte" });
  const cliente = criarCliente();
  const mapa = criarPainelMapa(aMapa, cliente, `Mapa de votos de ${c.nm_urna}`);
  const erroMapa = h("div");
  mapa.atualizar({ ...paramsComCargo(filtros), cargo: c.cargo, ano: String(c.ano), grupo: undefined, sq_candidato: String(c.sq_candidato), indicador: "penetracao", nivel: "municipio" })
    .catch((err: unknown) => { mostrarErro(erroMapa, err, () => { /* recarregar a tela refaz */ }); });
  destino.append(
    h("section", { className: "ficha" },
      h("h2", { textContent: c.nm_urna }),
      h("p", { textContent: `${c.partido.sigla} · ${c.cargo.toLowerCase()} · ${c.sg_uf} · ${String(c.ano)} · ${c.resultado ?? "resultado ainda não definido"}` }),
      aKpi,
      ...[avisosUi("candidato", ctx)].filter((x) => x !== null),
      h("h3", { textContent: "Votos por município" }), aBarras,
      h("h3", { textContent: "Mapa individual" }), erroMapa, aMapa,
      h("h3", { textContent: "Receitas" }), aReceita,
      rodapeUi("candidato", ctx),
    ),
  );
  return () => { k.destruir(); b.destruir(); e.destruir(); mapa.destruir(); };
}

export const tela: Tela = {
  titulo: "Candidato",
  render(container, estado) {
    const { filtros } = estado;
    const cliente = criarCliente();
    const conteudo = h("div");
    container.replaceChildren(titulo("Candidato"), cabecalhoDaTela("candidato"), conteudo);
    const [ano, sq] = filtros.candidato.split(":");
    const parar = carregar(
      conteudo,
      () => Promise.all([cliente.candidatos({ ...paramsDeFiltros(filtros), limite: "500" }), sq && ano ? cliente.ficha(Number(ano), sq) : Promise.resolve(null)]),
      ([r]) => (r.itens.length === 0 ? "Nenhum candidato encontrado para estes filtros." : null),
      ([r, ficha], destino) => {
        const seletor = campoSelect(
          "Candidato", "candidato",
          [{ valor: "", texto: "Escolha…" }, ...r.itens.map((c) => ({ valor: `${String(c.ano)}:${String(c.sq_candidato)}`, texto: c.nm_urna }))],
          filtros.candidato,
          // O hash é a fonte de verdade: a rota atualiza o store e a tela se redesenha (deep-link grátis).
          (v) => { window.location.hash = formatarHash("candidato", { ...filtros, candidato: v }); },
        );
        destino.append(h("div", { className: "controles" }, seletor.rotulo));
        if (!ficha) { destino.append(h("p", { className: "estado", textContent: "Escolha um candidato para ver a ficha." })); return; }
        return desenharFicha(destino, ficha, filtros);
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
