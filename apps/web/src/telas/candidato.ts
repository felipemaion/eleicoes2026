import { paramsMapaDoCandidato, textoForaDoMapa } from "../dados/abrangencia";
import { barrasMunicipios, filtrosDoCandidato, paramsDeFiltros } from "../dados/adaptadores";
import { criarCliente } from "../dados/cliente";
import type { Candidato, Ficha, LinkOficial } from "../dados/contrato";
import { render as renderBarras } from "../componentes/graficos/barras";
import { render as renderEmpilhado } from "../componentes/graficos/empilhado";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { formatarMoeda, formatarNumero } from "../formato";
import { formatarHash } from "../rotas";
import { campoSelect, h, titulo } from "./dom";
import { carregar, mostrarErro } from "./estados";
import { criarPainelMapa } from "./painel-mapa";
import { seguirCandidato } from "./recorte";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const DATASETS_VOTOS = ["votacao_candidato_munzona", "detalhe_votacao_munzona", "votacao_secao"];
const DATASETS_CONTAS = ["prestacao_contas"];

/** Gastos completos de um candidato: contratado, pago, dívida e custo por voto com e sem repasses. */
function secaoGastos(f: Ficha, ctx: Parameters<typeof ajuda>[1]): HTMLElement {
  const g = f.gastos;
  const secao = h("section", { className: "ficha-gastos" }, h("h3", {}, "Gastos de campanha ", fonteUi(f.fontes, DATASETS_CONTAS)));
  if (!g) {
    secao.append(h("p", { className: "nota", textContent: "Sem prestação de contas publicada para esta candidatura." }));
    return secao;
  }
  const kpis: Kpi[] = [
    { rotulo: "Contratado", valor: g.despesa_contratada, formato: "moeda", unidade: "despesa de campanha contratada" },
    { rotulo: "Pago", valor: g.despesa_paga, formato: "moeda", unidade: "despesa de campanha efetivamente paga" },
    { rotulo: "Dívida", valor: g.divida, formato: "moeda", unidade: "contratado − pago" },
    { rotulo: "Repasses a terceiros", valor: g.repasses_contratados, formato: "moeda", unidade: `contratados (pagos: ${formatarMoeda(g.repasses_pagos)})` },
    { rotulo: "Receita total", valor: g.receita_total, formato: "moeda", unidade: "todas as fontes" },
  ];
  const sem = (rotulo: string, v: number | null, unidade: string): void => { if (v !== null) kpis.push({ rotulo, ajuda: "custo_por_voto", valor: v, formato: "moeda", unidade }); };
  sem("Custo por voto contratado, sem repasses", g.custo_voto_contratado, "R$ contratados ÷ votos, sem repasses");
  sem("Custo por voto contratado, com repasses", g.custo_voto_contratado_com_repasses, "R$ contratados + repasses ÷ votos");
  sem("Custo por voto pago, sem repasses", g.custo_voto_pago, "R$ pagos ÷ votos, sem repasses");
  sem("Custo por voto pago, com repasses", g.custo_voto_pago_com_repasses, "R$ pagos + repasses ÷ votos");
  const area = h("div");
  renderKpi(area, kpis, { ajuda: (chave) => ajuda(chave, ctx) });
  secao.append(area, h("p", { className: "nota", textContent: g.explicacao_repasses }));
  return secao;
}

/** Botões para as páginas oficiais (conferência independente). Link não verificado diz o que conferir. */
function secaoLinks(links: readonly LinkOficial[]): HTMLElement | null {
  if (links.length === 0) return null;
  return h("section", { className: "ficha-links" },
    h("h3", { textContent: "Confira nas páginas oficiais do TSE" }),
    h("ul", { className: "lista-links" }, ...links.map((l) => h("li", {},
      h("a", { className: "botao-link", href: l.url, target: "_blank", rel: "noopener noreferrer", textContent: l.rotulo }),
      ...(l.verificado ? [] : [h("span", { className: "nota", textContent: ` Link não verificado automaticamente. ${l.nota ?? ""}` })]),
    ))),
  );
}

function desenharFicha(destino: HTMLElement, f: Ficha): () => void {
  const c = f.candidato;
  const kpis: Kpi[] = [{ rotulo: "Votos", fonte: "votos", valor: c.votos, formato: "inteiro" }];
  if (c.pct_validos !== null) kpis.push({ rotulo: "% dos válidos", ajuda: "pct_validos", fonte: "votos", valor: c.pct_validos, formato: "pontos", unidade: "% dos votos válidos" });
  if (c.penetracao !== null) kpis.push({ rotulo: "Penetração", ajuda: "penetracao", fonte: "votos", valor: c.penetracao, formato: "permil", unidade: "votos por mil aptos" });
  const aKpi = h("div");
  const aBarras = h("div");
  const aReceita = h("div");
  const aMapa = h("div", { className: "mapa-area" });
  const ctx = { dt_geracao: f.dt_geracao, mes_base_ipca: f.base_ipca ?? undefined, contas_parciais: f.contas_parciais };
  const fonteDe = (chave: string): HTMLElement => fonteUi(f.fontes, chave === "votos" ? DATASETS_VOTOS : DATASETS_CONTAS);
  const k = renderKpi(aKpi, kpis, { ajuda: (chave) => ajuda(chave, ctx), fonte: fonteDe });
  const b = renderBarras(aBarras, barrasMunicipios(f, 10), { titulo: "Municípios com mais votos", formato: formatarNumero, colunaValor: "Votos" });
  const e = renderEmpilhado(aReceita, f.receitas ? [{ rotulo: c.nm_urna, valores: f.receitas.por_categoria }] : [], { titulo: "Receita por fonte" });
  const cliente = criarCliente();
  const mapa = criarPainelMapa(aMapa, cliente, `Mapa de votos de ${c.nm_urna}`);
  const erroMapa = h("div");
  const foraDoMapa = h("div");
  // Ano, cargo e UF vêm do candidato (presidente = país todo): os filtros da tela podem ser de outro recorte.
  // Enquadra antes de colorir: o mapa só é "pronto" com a região do candidato já à vista.
  mapa.definirAbrangencia(c.abrangencia)
    .then(() => mapa.atualizar(paramsMapaDoCandidato(c)))
    .then((r) => {
      const fora = r ? textoForaDoMapa(r.votos_fora_do_mapa) : null;
      if (fora) foraDoMapa.replaceChildren(h("p", { className: "nota", textContent: fora }));
    })
    .catch((err: unknown) => { mostrarErro(erroMapa, err, () => { /* recarregar a tela refaz */ }); });
  destino.append(
    h("section", { className: "ficha" },
      h("h2", { textContent: c.nm_urna }),
      h("p", { textContent: `${c.partido.sigla} · ${c.cargo.toLowerCase()} · ${c.sg_uf} · ${String(c.ano)} · ${c.resultado ?? "resultado ainda não definido"}` }),
      aKpi,
      ...[avisosUi("candidato", ctx)].filter((x) => x !== null),
      h("h3", { textContent: "Votos por município" }), aBarras,
      h("h3", { textContent: "Mapa individual" }), erroMapa, aMapa, foraDoMapa,
      secaoGastos(f, ctx),
      h("h3", {}, "Receitas ", fonteUi(f.fontes, DATASETS_CONTAS)), aReceita,
      ...[secaoLinks(f.links)].filter((x) => x !== null),
      rodapeUi("candidato", ctx),
    ),
  );
  return () => { k.destruir(); b.destruir(); e.destruir(); mapa.destruir(); };
}

/** A lista do recorte pode não conter o candidato vindo da busca (outro partido/ano): ele entra à parte. */
function opcoesDoSeletor(itens: readonly Candidato[], ficha: Ficha | null): { valor: string; texto: string }[] {
  const lista = itens.map((c) => ({ valor: `${String(c.ano)}:${String(c.sq_candidato)}`, texto: c.nm_urna }));
  if (ficha) {
    const valor = `${String(ficha.candidato.ano)}:${String(ficha.candidato.sq_candidato)}`;
    if (!lista.some((o) => o.valor === valor)) lista.unshift({ valor, texto: ficha.candidato.nm_urna });
  }
  return [{ valor: "", texto: "Escolha…" }, ...lista];
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
      async () => {
        const ficha = sq && ano ? await cliente.ficha(Number(ano), sq) : null;
        // A lista do seletor é do recorte do candidato (cargo/UF/ano dele), não do filtro que estiver na barra.
        const recorte = ficha ? { ...filtros, ...filtrosDoCandidato(ficha.candidato) } : filtros;
        return [await cliente.candidatos({ ...paramsDeFiltros(recorte), limite: "500" }), ficha] as const;
      },
      // Candidato fixado (vindo da busca) vale mesmo que a lista do recorte esteja vazia.
      ([r, ficha]) => (r.itens.length === 0 && !ficha ? "Nenhum candidato encontrado para estes filtros." : null),
      ([r, ficha], destino) => {
        const seletor = campoSelect(
          "Candidato", "candidato",
          opcoesDoSeletor(r.itens, ficha),
          filtros.candidato,
          // O hash é a fonte de verdade: a rota atualiza o store e a tela se redesenha (deep-link grátis).
          (v) => { window.location.hash = formatarHash("candidato", { ...filtros, candidato: v }); },
        );
        destino.append(h("div", { className: "controles" }, seletor.rotulo));
        if (!ficha) { destino.append(h("p", { className: "estado", textContent: "Escolha um candidato para ver a ficha." })); return; }
        seguirCandidato(ficha.candidato);
        return desenharFicha(destino, ficha);
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
