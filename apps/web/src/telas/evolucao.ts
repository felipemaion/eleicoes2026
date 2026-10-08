import { cargoDaApi, escalaIgualNosDoisAnos, mapaDeDiferenca, penetracaoDosAnos } from "../dados/adaptadores";
import { criarCliente, ErroApi, type ClienteApi } from "../dados/cliente";
import { formatarLado, fraseResumo, nomeDoLado, paramsComparativo, parseLado, resolverLados, type Frase, type Lado, type LadosResolvidos } from "../dados/comparador-logica";
import type { RespostaComparativo, RespostaGrupos } from "../dados/contrato";
import { ROTULO_CARGO, rotuloDaUf } from "../filtros-logica";
import { formatarHash } from "../rotas";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import type { MetaIndicador } from "../componentes/escalas/escalas";
import { formatarPermil } from "../formato";
import { h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { montarMapa } from "./mapa-embutido";
import { criarCartao } from "./comparador-cartao";
import { tabelaCandidaturas, type CandidaturaFicha } from "./evolucao-candidaturas";
import { TEXTOS_COMPARADOR as T } from "./textos-comparador";
import { ajuda, avisosUi, cabecalhoDaTela, fonteUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const META_PENETRACAO: MetaIndicador = { nome: "Penetração", tipo: "taxa", unidade: "‰", denominador: "eleitores aptos do município" };
const DATASETS_VOTOS = ["votacao_candidato_munzona", "detalhe_votacao_munzona", "votacao_secao"];

/** Fichas já buscadas (`ano:sq`): dão nome aos chips e linhas à tabela sem repetir a consulta ao reabrir a tela. */
const fichas = new Map<string, CandidaturaFicha>();

function figura(legenda: string): { fig: HTMLElement; area: HTMLElement } {
  const area = h("div", { className: "mapa-area" });
  return { fig: h("figure", {}, h("figcaption", { textContent: legenda }), area), area };
}

/** `/comparativo` responde 422 quando um lado não tem candidaturas no cargo/UF: é um caso de uso, não um erro técnico. */
type ResultadoComparativo = { c: RespostaComparativo } | { c: null; codigo: string | null };
async function comparativoOuNulo(cliente: ClienteApi, params: Parameters<ClienteApi["comparativo"]>[0]): Promise<ResultadoComparativo> {
  try {
    return { c: await cliente.comparativo(params) };
  } catch (e) {
    if (e instanceof ErroApi && e.status === 422) return { c: null, codigo: e.codigo };
    throw e;
  }
}

/** Códigos de 422 que apontam para os lados de candidatos: a mensagem vai no cartão deles. */
const COD_SQ_FORA = "sq_fora_do_recorte";
const mensagemGeral = (codigo: string | null, lados: LadosResolvidos): string =>
  codigo === COD_SQ_FORA && (lados.de.tipo === "candidatos" || lados.para.tipo === "candidatos") ? T.erroSqForaGeral : T.erro422;

const sqsDe = (l: Lado): string[] => (l.tipo === "candidatos" ? l.sqs : []);

async function carregarFichas(cliente: ClienteApi, lados: LadosResolvidos): Promise<void> {
  const faltam = [...sqsDe(lados.de).map((sq) => [2022, sq] as const), ...sqsDe(lados.para).map((sq) => [2026, sq] as const)].filter(([a, sq]) => !fichas.has(`${String(a)}:${sq}`));
  await Promise.all(faltam.map(async ([ano, sq]) => {
    try { fichas.set(`${String(ano)}:${sq}`, (await cliente.ficha(ano, sq)).candidato); } catch (e) { console.error("Ficha indisponível:", e); }
  }));
}

function nomesDoAno(ano: number, lado: Lado): Map<string, string> {
  const m = new Map<string, string>();
  for (const sq of sqsDe(lado)) { const f = fichas.get(`${String(ano)}:${sq}`); if (f) m.set(sq, f.nm_urna); }
  return m;
}

function elementoFrase(f: Frase): HTMLElement {
  const p = h("p", { className: "frase-resumo" }, "Comparando ", h("strong", { textContent: f.de }), " (2022) com ", h("strong", { textContent: f.para }), ` (2026) · ${f.contexto}`);
  if (f.contagem) p.append(h("span", { className: "frase-contagem", textContent: ` — ${f.contagem}` }));
  return p;
}

export const tela: Tela = {
  titulo: "Evolução 2022×2026",
  render(container, { filtros }) {
    const cliente = criarCliente();
    const cargoApi = cargoDaApi(filtros.cargo);
    const contexto = `${ROTULO_CARGO[filtros.cargo]} · ${rotuloDaUf(filtros.uf)}`;
    const raiz = h("div");
    container.replaceChildren(titulo("Evolução 2022×2026"), cabecalhoDaTela("evolucao"), raiz);
    const irPara = (campos: Partial<typeof filtros>): void => { window.location.hash = formatarHash("evolucao", { ...filtros, ...campos }); };

    const parar = carregar(
      raiz,
      async () => {
        const g = await cliente.grupos();
        const lados = resolverLados(parseLado(filtros.de), parseLado(filtros.para), g.comparacoes, filtros.grupo);
        await carregarFichas(cliente, lados);
        return { g, lados };
      },
      () => null,
      ({ g, lados }, destino) => desenhar(destino, g, lados),
    );

    function desenhar(destino: HTMLElement, g: RespostaGrupos, lados: LadosResolvidos): () => void {
      const grupos = g.grupos;
      const nomes = { 2022: nomesDoAno(2022, lados.de), 2026: nomesDoAno(2026, lados.para) };
      const indicados = new Set<string>();
      for (const [chave, f] of fichas) if (f.indicado) indicados.add(chave.split(":")[1] ?? "");
      const nomeDe = nomeDoLado(lados.de, grupos, nomes[2022]);
      const nomePara = nomeDoLado(lados.para, grupos, nomes[2026]);
      const entrada = { de: nomeDe, para: nomePara, cargo: ROTULO_CARGO[filtros.cargo], uf: rotuloDaUf(filtros.uf) };
      const areaFrase = h("div", { className: "resumo-comparacao" });
      areaFrase.setAttribute("aria-live", "polite");
      const desenharFrase = (nDe: number | null, nPara: number | null): void => { areaFrase.replaceChildren(elementoFrase(fraseResumo({ ...entrada, nDe, nPara }))); };
      desenharFrase(null, null);

      const slotDe = h("div");
      const slotPara = h("div");
      const areaCartoes = h("div", { className: "cartoes-lados" }, slotDe, h("span", { className: "cartoes-seta", textContent: "→" }), slotPara);
      areaCartoes.querySelector(".cartoes-seta")?.setAttribute("aria-hidden", "true");
      const lado = (ano: 2022 | 2026): { grupos: typeof grupos; lado: Lado; nome: string; nomes: Map<string, string>; indicados: Set<string> } =>
        ({ grupos: grupos.filter((x) => x.ano === ano), lado: ano === 2022 ? lados.de : lados.para, nome: ano === 2022 ? nomeDe : nomePara, nomes: nomes[ano], indicados });
      const cartao = (slot: HTMLElement, ano: 2022 | 2026, campo: "de" | "para"): (() => void) =>
        criarCartao(slot, { ano, cliente, cargo: cargoApi, uf: filtros.uf, ...lado(ano), aplicar: (l) => { irPara({ [campo]: formatarLado(l) }); } });
      const pararCartoes = [cartao(slotDe, 2022, "de"), cartao(slotPara, 2026, "para")];

      const limpar = h("button", { type: "button", textContent: T.limpar });
      limpar.addEventListener("click", () => { irPara({ de: "", para: "" }); });
      const personalizado = filtros.de !== "" || filtros.para !== "";
      const areaResultado = h("div");
      destino.append(areaFrase, areaCartoes, ...(personalizado ? [h("p", {}, limpar)] : []), nota(`Recorte: ${contexto}. Mude cargo e UF na barra de filtros.`), areaResultado);

      const pararResultado = carregar(
        areaResultado,
        async () => {
          const r = await comparativoOuNulo(cliente, paramsComparativo(lados.de, lados.para, cargoApi, filtros.uf, g.comparacoes));
          for (const x of areaCartoes.querySelectorAll(".cartao-erro-api")) x.remove();
          if (r.c === null && r.codigo === COD_SQ_FORA) {
            for (const [slot, l] of [[slotDe, lados.de], [slotPara, lados.para]] as const) {
              if (l.tipo === "candidatos") slot.append(h("p", { className: "cartao-erro cartao-erro-api", role: "status", textContent: T.erroSqLado }));
            }
          }
          return r;
        },
        (r) => (r.c === null ? mensagemGeral(r.codigo, lados) : r.c.municipios.length === 0 ? "Sem dados comparáveis entre 2022 e 2026 para estes filtros." : null),
        ({ c }, alvo) => {
          if (c === null) return undefined;
          desenharFrase(c.n_de, c.n_para);
          return desenharResultado(alvo, c, nomeDe, nomePara, lados);
        },
      );
      return () => { pararResultado(); for (const p of pararCartoes) p(); };
    }

    function desenharResultado(destino: HTMLElement, c: RespostaComparativo, nomeDe: string, nomePara: string, lados: LadosResolvidos): () => void {
      const { kpis: k } = c;
      const itens: Kpi[] = [];
      if (k.penetracao_de !== null) itens.push({ rotulo: "Penetração em 2022", ajuda: "penetracao", fonte: "votos", valor: k.penetracao_de, formato: "permil", unidade: `votos por mil aptos · ${nomeDe}` });
      if (k.penetracao_para !== null) itens.push({ rotulo: "Penetração em 2026", ajuda: "penetracao", fonte: "votos", valor: k.penetracao_para, formato: "permil", unidade: `votos por mil aptos · ${nomePara}` });
      if (k.delta_penetracao !== null) itens.push({ rotulo: "Mudança na penetração", ajuda: "evolucao", valor: k.delta_penetracao, formato: "permil", unidade: "‰ — 2026 menos 2022 (métrica-âncora)" });
      if (k.swing_pp !== null) itens.push({ rotulo: "Swing (% válidos)", ajuda: "evolucao", valor: k.swing_pp, formato: "pontos", unidade: "pontos percentuais, 2026 vs 2022" });
      if (k.retencao !== null) itens.push({ rotulo: "Retenção", ajuda: "evolucao", valor: k.retencao, formato: "percentual", unidade: "votos de 2026 ÷ votos de 2022 (nos municípios comparáveis)" });
      if (k.ganho_absoluto !== null) itens.push({ rotulo: "Ganho absoluto", ajuda: "evolucao", valor: k.ganho_absoluto, formato: "inteiro", unidade: "votos a mais que em 2022" });
      const kpis = h("div");
      const ctx = { dt_geracao: c.dt_geracao };
      const kpi = renderKpi(kpis, itens, { ajuda: (x) => ajuda(x, ctx), fonte: () => fonteUi(c.fontes, DATASETS_VOTOS) });

      const a = figura(`2022 · ${nomeDe}`);
      const d = figura(`2026 · ${nomePara}`);
      const dif = figura("Diferença (Δ penetração por AMC)");
      const avisos = avisosUi("evolucao", ctx);
      const linhas = [...sqsDe(lados.de).map((sq) => fichas.get(`2022:${sq}`)), ...sqsDe(lados.para).map((sq) => fichas.get(`2026:${sq}`))].filter((x): x is CandidaturaFicha => x !== undefined);
      destino.append(
        h("h2", { textContent: "Números principais" }), kpis,
        h("h2", { textContent: "Mapas lado a lado" }),
        h("div", { className: "mapas-3" }, a.fig, d.fig, dif.fig),
        nota("Os mapas de 2022 e 2026 usam as mesmas quebras de cor."),
        ...[tabelaCandidaturas(linhas)].filter((x) => x !== null),
        ...(avisos ? [h("details", { className: "notas-dados" }, h("summary", { textContent: T.notasDados }), avisos, ...(c.mesmos_candidatos ? [nota("Comparação restrita aos candidatos que concorreram nos dois anos.")] : []), nota("Zonas eleitorais não são comparadas entre anos (rezoneamento); a comparação é por município agregado (AMC)."))] : []),
        rodapeUi("evolucao", ctx),
      );

      let vivo = true;
      const nomesMun = new Map(c.municipios.map((m) => [String(m.cd_amc), m.nome]));
      const detalhes = (valores: Readonly<Record<string, number>>): Record<string, { nome: string; taxa: number }> =>
        Object.fromEntries(Object.entries(valores).map(([id, taxa]) => [id, { nome: nomesMun.get(id) ?? id, taxa }]));
      const pen = penetracaoDosAnos(c);
      const escalas = escalaIgualNosDoisAnos(pen.antes, pen.depois);
      const diff = mapaDeDiferenca(c);
      const opcoes = { ano: c.para.ano, formatarTaxa: formatarPermil };
      const montagens = [
        montarMapa(a.area, `Mapa de penetração, 2022 · ${nomeDe}`, opcoes).then((m) => { if (vivo) m.definirValores(pen.antes, escalas.antes, META_PENETRACAO, detalhes(pen.antes)); return m; }),
        montarMapa(d.area, `Mapa de penetração, 2026 · ${nomePara}`, opcoes).then((m) => { if (vivo) m.definirValores(pen.depois, escalas.depois, META_PENETRACAO, detalhes(pen.depois)); return m; }),
        montarMapa(dif.area, "Mapa da diferença de penetração", opcoes).then((m) => { if (vivo) m.definirValores(diff.valores, diff.escala, diff.meta, diff.detalhes); return m; }),
      ];
      Promise.all(montagens).catch((e: unknown) => { if (vivo) destino.append(h("p", { role: "alert", textContent: `Não foi possível desenhar os mapas: ${e instanceof Error ? e.message : String(e)}` })); });
      return () => {
        vivo = false;
        kpi.destruir();
        for (const p of montagens) void p.then((m) => { m.destruir(); }, () => { /* nunca montou */ });
      };
    }

    return () => { parar(); container.replaceChildren(); };
  },
};
