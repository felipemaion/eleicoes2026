import { cargoDaApi, escalaIgualNosDoisAnos, mapaDeDiferenca, paramsComCargo, penetracaoDosAnos } from "../dados/adaptadores";
import { criarCliente, type ClienteApi } from "../dados/cliente";
import type { PessoaEvolucao, RespostaComparativo } from "../dados/contrato";
import { linhasComparativas, paramsPessoas, parsePessoas, type Penetracoes } from "../dados/evolucao-logica";
import { ROTULO_CARGO, rotuloDaUf } from "../filtros-logica";
import { formatarHash } from "../rotas";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import type { MetaIndicador } from "../componentes/escalas/escalas";
import { formatarPermil } from "../formato";
import { campoSelect, h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { montarMapa } from "./mapa-embutido";
import { criarTabelaPessoas } from "./evolucao-tabela";
import { criarSelecao } from "./evolucao-selecao";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const META_PENETRACAO: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "‰", denominador: "eleitores aptos do município" };

function figura(legenda: string): { fig: HTMLElement; area: HTMLElement } {
  const area = h("div", { className: "mapa-area" });
  return { fig: h("figure", {}, h("figcaption", { textContent: legenda }), area), area };
}

/** Penetração por candidato vem da ficha de cada ano (2 chamadas por pessoa): só até este limite. */
const MAX_PENETRACAO = 12;
const DATASETS_VOTOS = ["votacao_candidato_munzona", "detalhe_votacao_munzona", "votacao_secao"];

/** `/comparativo` por seleção responde 422 quando ninguém tem par no cargo/UF: é um caso de uso, não um erro técnico. */
async function comparativoDaSelecao(cliente: ClienteApi, ids: readonly string[], cargo: string, uf: string): Promise<RespostaComparativo | null> {
  try {
    return await cliente.comparativo(paramsPessoas(ids, cargo, uf));
  } catch (e) {
    if (e instanceof Error && e.message.endsWith(": 422")) return null;
    throw e;
  }
}

async function buscarPenetracoes(cliente: ClienteApi, pessoas: readonly PessoaEvolucao[]): Promise<Penetracoes> {
  const pen = async (ano: number, sq: number): Promise<number | null> => {
    try { return (await cliente.ficha(ano, sq)).candidato.penetracao; } catch { return null; }
  };
  const pares = await Promise.all(pessoas.map(async (p) => [p.pessoa_id_publico, { de: await pen(p.de.ano, p.de.sq_candidato), para: await pen(p.para.ano, p.para.sq_candidato) }] as const));
  return Object.fromEntries(pares);
}

/** Comparação que desemboca no grupo escolhido nos filtros; sem ela, a primeira declarada. */
function padraoDeComparacao(comparacoes: readonly { id: string; para: string }[], grupo: string): string {
  return (comparacoes.find((c) => c.para === grupo) ?? comparacoes[0])?.id ?? "";
}

export const tela: Tela = {
  titulo: "Evolução 2022×2026",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const areaSelecao = h("div");
    const conteudo = h("div");
    container.replaceChildren(titulo("Evolução 2022×2026"), cabecalhoDaTela("evolucao"), areaSelecao, conteudo);
    const ids = parsePessoas(filtros.pessoas);
    const cargoApi = cargoDaApi(filtros.cargo);
    const baseLista = { cargo: cargoApi, ...(filtros.uf !== "BR" ? { uf: filtros.uf } : {}) };
    const pararSelecao = criarSelecao(areaSelecao, {
      cliente,
      params: baseLista,
      recorte: `${ROTULO_CARGO[filtros.cargo]} · ${rotuloDaUf(filtros.uf)}`,
      selecionadas: ids,
      aplicar: (novos) => { window.location.hash = formatarHash("evolucao", { ...filtros, pessoas: novos.join(",") }); },
    });
    let comparacao = "";
    let parar = (): void => { /* ainda sem busca */ };

    const iniciar = (focar?: string): void => {
      parar();
      parar = carregar(
        conteudo,
        async () => {
          // `comparacao` é obrigatória na API: sem escolha do usuário, usa a que termina no grupo filtrado (senão, a primeira).
          if (ids.length > 0) {
            const [c, lista] = await Promise.all([comparativoDaSelecao(cliente, ids, cargoApi, filtros.uf), cliente.pessoas({ ...baseLista, limite: "200" })]);
            return { c, g: null, lista: lista.itens };
          }
          const g = await cliente.grupos();
          comparacao = comparacao || padraoDeComparacao(g.comparacoes, filtros.grupo);
          const c = await cliente.comparativo({ ...paramsComCargo(filtros), comparacao: comparacao || undefined });
          return { c, g, lista: [] as PessoaEvolucao[] };
        },
        ({ c }) => (c === null ? `Nenhum dos candidatos escolhidos concorreu a ${ROTULO_CARGO[filtros.cargo].toLowerCase()} nos dois anos neste recorte (${rotuloDaUf(filtros.uf)}). Troque cargo ou UF na barra de filtros, ou escolha outras pessoas.` : c.municipios.length === 0 ? "Sem dados comparáveis entre 2022 e 2026 para estes filtros." : null),
        ({ c: cNulo, g, lista }, destino) => {
          if (cNulo === null) return undefined;
          const c = cNulo;
          comparacao = comparacao || (g ? padraoDeComparacao(g.comparacoes, filtros.grupo) : "");
          const seletor = g ? campoSelect("Comparar", "comparacao", g.comparacoes.map((x) => ({ valor: x.id, texto: x.rotulo })), comparacao, (v) => { comparacao = v; iniciar("comparacao"); }) : null;
          const { de, para, kpis: k } = c;
          const itens: Kpi[] = [];
          if (k.penetracao_de !== null) itens.push({ rotulo: `Penetração ${de.rotulo}`, ajuda: "penetracao", fonte: "votos", valor: k.penetracao_de, formato: "permil", unidade: "votos por mil aptos" });
          if (k.penetracao_para !== null) itens.push({ rotulo: `Penetração ${para.rotulo}`, ajuda: "penetracao", fonte: "votos", valor: k.penetracao_para, formato: "permil", unidade: "votos por mil aptos" });
          if (k.delta_penetracao !== null) itens.push({ rotulo: "Δ penetração", ajuda: "evolucao", valor: k.delta_penetracao, formato: "permil", unidade: "‰ — métrica-âncora (depois − antes)" });
          if (k.swing_pp !== null) itens.push({ rotulo: "Swing (% válidos)", ajuda: "evolucao", valor: k.swing_pp, formato: "pontos", unidade: "pontos percentuais" });
          if (k.retencao !== null) itens.push({ rotulo: "Retenção", ajuda: "evolucao", valor: k.retencao, formato: "percentual", unidade: "votos depois ÷ votos antes (nos municípios comparáveis)" });
          if (k.ganho_absoluto !== null) itens.push({ rotulo: "Ganho absoluto", ajuda: "evolucao", valor: k.ganho_absoluto, formato: "inteiro", unidade: "votos a mais que antes" });
          const kpis = h("div");
          const ctx = { dt_geracao: c.dt_geracao };
          const kpi = renderKpi(kpis, itens, { ajuda: (k) => ajuda(k, ctx), fonte: () => fonteUi(c.fontes, DATASETS_VOTOS) });
          
          const areaTabela = h("section", { className: "evolucao-tabela" });
          const a = figura(de.rotulo);
          const d = figura(para.rotulo);
          const dif = figura("Diferença (Δ penetração por AMC)");
          destino.append(
            ...[avisosUi("evolucao", ctx)].filter((x) => x !== null),
            ...(seletor ? [h("div", { className: "controles" }, seletor.rotulo)] : [h("h2", { textContent: `Comparando ${String(ids.length)} ${ids.length === 1 ? "candidato" : "candidatos"}` })]),
            kpis,
            h("h2", { textContent: "Mapas lado a lado" }),
            h("div", { className: "mapas-3" }, a.fig, d.fig, dif.fig),
            nota("Os mapas de 2022 e 2026 usam as mesmas quebras de cor. Zonas eleitorais não são comparadas entre anos (rezoneamento); a comparação é por município agregado (AMC)."),
            ...(c.mesmos_candidatos ? [nota("Comparação restrita aos candidatos que concorreram nos dois anos.")] : []),
            ...(ids.length > 0 ? [areaTabela] : []),
            rodapeUi("evolucao", ctx),
          );
          if (focar) destino.querySelector<HTMLElement>(`[name=${focar}]`)?.focus();

          let vivo = true;
          if (ids.length > 0) montarTabela(areaTabela, ids, lista, cliente, () => vivo);
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
    return () => { parar(); pararSelecao(); container.replaceChildren(); };
  },
};

/** Tabela 2022 × 2026 das pessoas escolhidas; a penetração chega depois (fichas) e preenche as células. */
function montarTabela(destino: HTMLElement, ids: readonly string[], lista: readonly PessoaEvolucao[], cliente: ClienteApi, vivo: () => boolean): void {
  const escolhidas = ids.flatMap((id) => lista.find((p) => p.pessoa_id_publico === id) ?? []).filter((p) => p.comparavel);
  const faltam = ids.length - escolhidas.length;
  destino.append(h("h2", { textContent: "Cada candidato, 2022 × 2026" }));
  if (escolhidas.length === 0) {
    destino.append(nota("Os candidatos escolhidos não estão na lista carregada para este recorte; refaça a busca acima."));
    return;
  }
  const tabela = criarTabelaPessoas(linhasComparativas(escolhidas, {}));
  const aviso = h("p", { className: "nota", role: "status" });
  destino.append(tabela.elemento, aviso);
  if (faltam > 0) aviso.textContent = `${String(faltam)} ${faltam === 1 ? "pessoa escolhida está" : "pessoas escolhidas estão"} fora do comparativo ou da lista carregada para este recorte.`;
  if (escolhidas.length > MAX_PENETRACAO) {
    aviso.textContent += ` A penetração por candidato aparece para até ${String(MAX_PENETRACAO)} escolhidos (cada um exige duas consultas).`;
    return;
  }
  aviso.textContent += " Penetração: carregando…";
  void buscarPenetracoes(cliente, escolhidas).then((pen) => {
    if (!vivo()) return;
    tabela.atualizar(linhasComparativas(escolhidas, pen));
    const sem = Object.values(pen).filter((x) => x.de === null || x.para === null).length;
    aviso.textContent = (faltam > 0 ? aviso.textContent.replace(" Penetração: carregando…", "") : "") + (sem > 0 ? ` Penetração indisponível em ${String(sem)} ${sem === 1 ? "candidato" : "candidatos"} (sem votação ou denominador no ano).` : "");
  });
}
