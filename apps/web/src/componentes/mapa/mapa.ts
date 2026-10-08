/**
 * Mapa MapLibre reutilizável. Geometria carregada uma vez por nível; valores entram por
 * `feature-state`, então trocar de indicador/ano nunca recarrega polígonos.
 */
import * as maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, Map as MapaGL, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import urlWorker from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { FeatureCollection } from "geojson";
import { Protocol } from "pmtiles";
import { formatarPercentual } from "../../formato";
import { PALETAS } from "../../paletas";
import { expressaoCor, validarCoropletico, type Escala, type MetaIndicador } from "../escalas/escalas";
import { criarLegenda } from "../escalas/legenda";
import { expressaoOpacidade, expressaoPesoCalor, expressaoRaioCirculo, soFinitos } from "./expressoes";
import { limitesDe, type Limites } from "./geo";
import { limitesDosIds } from "../../dados/limites-uf";
import { ancoraEm, corpoRico, encaixar } from "../ui/tooltip";
import { textoTooltip, type DetalheLocal } from "./tooltip";

/** Hachura diagonal 8×8 para áreas de n baixo; a cor vem do tema, então é lida na hora de desenhar. */
function imagemHachura(cor: string): { width: number; height: number; data: Uint8Array } {
  const t = 8;
  const c = document.createElement("canvas");
  c.width = t; c.height = t;
  const g = c.getContext("2d");
  if (!g) throw new Error("Canvas 2D indisponível: não dá para desenhar a hachura de n baixo.");
  g.strokeStyle = cor; g.lineWidth = 1.5;
  g.beginPath();
  // Três segmentos cobrem os cantos para a diagonal emendar entre ladrilhos.
  g.moveTo(-1, t + 1); g.lineTo(t + 1, -1); g.moveTo(-1, 1); g.lineTo(1, -1); g.moveTo(t - 1, t + 1); g.lineTo(t + 1, t - 1);
  g.stroke();
  return { width: t, height: t, data: new Uint8Array(g.getImageData(0, 0, t, t).data.buffer) };
}

/** Detalhe sem nome obrigatório: a API do mapa não manda nomes; eles vêm da geometria. */
export type DetalheParcial = Omit<DetalheLocal, "nome"> & { nome?: string };

export type Nivel = "municipio" | "zona" | "h3";

export type FonteGeometria =
  | { tipo: "geojson"; dados: FeatureCollection; idPropriedade: string }
  | { tipo: "pmtiles"; url: string; camadaFonte: string; idPropriedade: string; limites: Limites };

export interface OpcoesMapa {
  fontes: Partial<Record<Nivel, FonteGeometria>> & { municipio: FonteGeometria };
  nivelInicial?: Nivel;
  /** Formata a taxa exibida no tooltip e na legenda (fração → texto). */
  formatarTaxa?: (v: number) => string;
  rotuloAcessivel?: string;
  /** Clique, ou Enter/Espaço com uma área destacada pelo teclado. `id` é a chave do nível (IBGE, IBGE-zona, H3). */
  aoSelecionar?: (id: string, nivel: Nivel) => void;
}

export interface EstatisticasMapa {
  /** Quantas fontes de geometria foram adicionadas (não cresce ao trocar valores). */
  fontesCarregadas: number;
  atualizacoesDeValores: number;
}

export interface Mapa {
  /** Resolve quando o estilo base carregou. */
  readonly pronto: Promise<void>;
  /** Colore o nível atual. Recusa indicadores absolutos (use `definirPontos`). */
  definirValores(valores: Readonly<Record<string, number>>, escala: Escala, meta: MetaIndicador, detalhes?: Readonly<Record<string, DetalheParcial>>): void;
  definirNivel(nivel: Nivel): void;
  /**
   * Foca a região do candidato: enquadra `limites` (ou o país, se `null`) e esmaece as áreas fora da UF
   * (`codigoUf` = prefixo IBGE de 2 dígitos; `null` = nenhuma esmaecida).
   */
  definirAbrangencia(codigoUf: string | null, limites: Limites | null): void;
  /** Densidade: heatmap + círculos com raio ∝ √votos. Feature precisa da propriedade `votos`. */
  definirPontos(pontos: FeatureCollection): void;
  estatisticas(): EstatisticasMapa;
  destruir(): void;
}

// O empacotador não resolve o worker sozinho: sem isto os tiles nunca renderizam.
maplibregl.setWorkerUrl(urlWorker);

const PROTOCOLO_PMTILES = "pmtiles";
/** Menor zoom com feições nos PMTiles (`zoom_min` do ETL). Abaixo disso o mapa fica vazio, sem erro algum. */
const ZOOM_MIN_PMTILES = 3;
const IMAGEM_HACHURA = "hachura-n-baixo";
let protocoloRegistrado = false;
function registrarPmtiles(): void {
  if (protocoloRegistrado) return;
  const p = new Protocol();
  // O tipo de `data` do pmtiles é `unknown`; o MapLibre aceita ArrayBuffer/Uint8Array.
  maplibregl.addProtocol(PROTOCOLO_PMTILES, async (params, ac) => {
    const r = await p.tilev4(params, ac);
    return { data: r.data as Uint8Array, cacheControl: r.cacheControl ?? null, expires: r.expires ?? null };
  });
  protocoloRegistrado = true;
}

function cssVar(nome: string, padrao: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

function estiloBase(): StyleSpecification {
  return { version: 8, sources: {}, layers: [{ id: "fundo", type: "background", paint: { "background-color": cssVar("--cor-superficie", "#f4f6f8") } }] };
}

/** Chave da legenda para a hachura: o texto é o mesmo aviso público (textos.json › avisos.n_baixo). */
function legendaHachura(): HTMLElement {
  const p = document.createElement("p");
  p.className = "legenda-hachura";
  const amostra = document.createElement("span");
  amostra.className = "amostra-hachura";
  amostra.setAttribute("aria-hidden", "true");
  p.append(amostra, "Hachurado: menos de 20 votos esperados — estimativa instável.");
  return p;
}

export function criarMapa(container: HTMLElement, opcoes: OpcoesMapa): Mapa {
  const formatarTaxa = opcoes.formatarTaxa ?? formatarPercentual;
  if (Object.values(opcoes.fontes).some((f) => f.tipo === "pmtiles")) registrarPmtiles();

  const quadro = document.createElement("div");
  quadro.className = "mapa-quadro";
  quadro.tabIndex = 0;
  quadro.setAttribute("role", "group");
  quadro.setAttribute("aria-label", `${opcoes.rotuloAcessivel ?? "Mapa"}. Use as setas para percorrer as áreas e Esc para fechar o detalhe.`);
  const areaLegenda = document.createElement("div");
  areaLegenda.className = "mapa-legenda";
  const tooltip = document.createElement("div");
  tooltip.className = "tooltip mapa-tooltip";
  tooltip.id = `mapa-tooltip-${Math.random().toString(36).slice(2, 8)}`;
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  quadro.setAttribute("aria-describedby", tooltip.id);
  const tabela = document.createElement("details");
  tabela.className = "mapa-tabela";
  container.replaceChildren(quadro, areaLegenda, tabela);
  quadro.append(tooltip);

  const mapa: MapaGL = new maplibregl.Map({
    container: quadro,
    style: estiloBase(),
    bounds: limitesIniciais(opcoes.fontes[opcoes.nivelInicial ?? "municipio"] ?? opcoes.fontes.municipio),
    fitBoundsOptions: { padding: 24 },
    // Em tela estreita o enquadramento do Brasil cairia em zoom < 3, onde os tiles não têm polígonos.
    ...(Object.values(opcoes.fontes).some((f) => f.tipo === "pmtiles") ? { minZoom: ZOOM_MIN_PMTILES } : {}),
    attributionControl: { compact: true },
    cooperativeGestures: false,
    // O teclado é do quadro (setas percorrem as áreas); o canvas não deve virar um 2º foco.
    keyboard: false,
  });
  // O MapLibre deixa o canvas com tabindex=0 mesmo com keyboard:false; fora da ordem de Tab, o foco é só do quadro.
  mapa.getCanvas().tabIndex = -1;
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

  let carregado = false;
  const fila: (() => void)[] = [];
  const pronto = new Promise<void>((resolve) => {
    mapa.once("load", () => {
      carregado = true;
      fila.splice(0).forEach((f) => { f(); });
      resolve();
    });
  });
  const quandoPronto = (f: () => void): void => { if (carregado) f(); else fila.push(f); };

  let nivel: Nivel = opcoes.nivelInicial ?? "municipio";
  const adicionadas = new Set<Nivel>();
  const stats: EstatisticasMapa = { fontesCarregadas: 0, atualizacoesDeValores: 0 };
  const valoresPorNivel = new Map<Nivel, Record<string, number>>();
  const detalhesPorNivel = new Map<Nivel, Readonly<Record<string, DetalheParcial>>>();
  let metaAtual: MetaIndicador | null = null;
  let destacado: string | null = null;
  let abrangenciaUf: string | null = null;

  const idFonte = (n: Nivel): string => `geo-${n}`;
  const idFill = (n: Nivel): string => `fill-${n}`;
  const idLinha = (n: Nivel): string => `linha-${n}`;
  const idHachura = (n: Nivel): string => `hachura-${n}`;

  const ESMAECIDA = 0.12;
  const opacidadeFill = (idProp: string): number | ExpressionSpecification => expressaoOpacidade(idProp, abrangenciaUf, 0.92, ESMAECIDA) as number | ExpressionSpecification;
  const opacidadeLinha = (idProp: string): number | ExpressionSpecification => expressaoOpacidade(idProp, abrangenciaUf, 1, 0.15) as number | ExpressionSpecification;

  function garantirNivel(n: Nivel): FonteGeometria {
    const f = opcoes.fontes[n];
    if (!f) throw new Error(`Nível "${n}" sem fonte de geometria configurada.`);
    if (adicionadas.has(n)) return f;
    if (f.tipo === "geojson") mapa.addSource(idFonte(n), { type: "geojson", data: f.dados, promoteId: f.idPropriedade });
    else mapa.addSource(idFonte(n), { type: "vector", url: `${PROTOCOLO_PMTILES}://${f.url}`, promoteId: f.idPropriedade });
    const camada = f.tipo === "pmtiles" ? { "source-layer": f.camadaFonte } : {};
    const destaque: ExpressionSpecification = ["case", ["boolean", ["feature-state", "destaque"], false], 3, 0.6];
    mapa.addLayer({ id: idFill(n), type: "fill", source: idFonte(n), ...camada, paint: { "fill-color": cssVar("--cor-sem-dado", "#c3c9d0"), "fill-opacity": opacidadeFill(f.idPropriedade) } }, camadaPontosAcima());
    if (!mapa.hasImage(IMAGEM_HACHURA)) mapa.addImage(IMAGEM_HACHURA, imagemHachura(cssVar("--cor-texto", "#1b2430")));
    // fill-pattern não aceita feature-state, mas fill-opacity aceita: a hachura existe em todos e só aparece onde nbaixo.
    mapa.addLayer({
      id: idHachura(n), type: "fill", source: idFonte(n), ...camada,
      paint: { "fill-pattern": IMAGEM_HACHURA, "fill-opacity": ["case", ["boolean", ["feature-state", "nbaixo"], false], 0.55, 0] },
    }, camadaPontosAcima());
    mapa.addLayer({ id: idLinha(n), type: "line", source: idFonte(n), ...camada, paint: { "line-color": cssVar("--cor-texto-suave", "#4a5360"), "line-width": destaque, "line-opacity": opacidadeLinha(f.idPropriedade) } }, camadaPontosAcima());
    adicionadas.add(n);
    stats.fontesCarregadas += 1;
    ligarInteracao(n, f);
    return f;
  }

  function camadaPontosAcima(): string | undefined {
    return mapa.getLayer("pontos-calor") ? "pontos-calor" : undefined;
  }

  const colador = new Intl.Collator("pt-BR");
  const nomesGeo = new Map<Nivel, Map<string, string>>();
  const idsOrdenados = new Map<Nivel, string[]>();
  /** Nomes lidos dos tiles já carregados (PMTiles não têm a lista de feições de antemão). */
  const nomesVistos = new Map<Nivel, Map<string, string>>();

  function colherNomes(n: Nivel): void {
    const f = opcoes.fontes[n];
    if (f?.tipo !== "pmtiles" || !adicionadas.has(n)) return;
    let vistos = nomesVistos.get(n);
    if (!vistos) { vistos = new Map(); nomesVistos.set(n, vistos); }
    const antes = vistos.size;
    for (const x of mapa.querySourceFeatures(idFonte(n), { sourceLayer: f.camadaFonte })) {
      const nome: unknown = x.properties["nome"];
      const id: unknown = x.properties[f.idPropriedade];
      if (typeof nome === "string" && (typeof id === "string" || typeof id === "number")) vistos.set(String(id), nome);
    }
    // Ordem do teclado depende dos nomes: refaz quando aparecem novos.
    if (vistos.size !== antes) idsOrdenados.delete(n);
  }
  const aoOciosoColherNomes = (): void => { colherNomes(nivel); };
  mapa.on("idle", aoOciosoColherNomes);

  /** id→nome indexado uma vez por nível (antes era `find` linear a cada comparação do sort). */
  function nomesDaGeometria(n: Nivel): Map<string, string> {
    let m = nomesGeo.get(n);
    if (m) return m;
    m = new Map();
    const f = opcoes.fontes[n];
    if (f?.tipo === "geojson") {
      for (const x of f.dados.features) {
        const nome: unknown = x.properties?.["nome"];
        if (typeof nome === "string") m.set(String(x.properties?.[f.idPropriedade]), nome);
      }
    }
    nomesGeo.set(n, m);
    return m;
  }

  function nomeDe(n: Nivel, id: string): string {
    return detalhesPorNivel.get(n)?.[id]?.nome ?? nomesDaGeometria(n).get(id) ?? nomesVistos.get(n)?.get(id) ?? id;
  }

  function ordenados(n: Nivel): string[] {
    let ids = idsOrdenados.get(n);
    if (!ids) {
      const nomes = new Map(Object.keys(valoresPorNivel.get(n) ?? {}).map((id) => [id, nomeDe(n, id)]));
      ids = [...nomes.keys()].sort((x, y) => colador.compare(nomes.get(x) ?? x, nomes.get(y) ?? y));
      idsOrdenados.set(n, ids);
    }
    return ids;
  }

  function mostrarTooltip(id: string, x: number, y: number): void {
    if (!metaAtual) return;
    const valor = valoresPorNivel.get(nivel)?.[id];
    const d = detalhesPorNivel.get(nivel)?.[id];
    const base: DetalheLocal = { ...(valor === undefined ? {} : { taxa: valor }), ...d, nome: nomeDe(nivel, id) };
    const c = textoTooltip(base, { unidade: metaAtual.unidade, formatarTaxa });
    tooltip.replaceChildren(corpoRico(c));
    posicionarTooltip(x, y);
  }

  function posicionarTooltip(x: number, y: number): void {
    tooltip.hidden = false;
    // Coordenadas do mapa → viewport: o balão é `position: fixed` para nunca ser cortado pelo quadro.
    const q = quadro.getBoundingClientRect();
    encaixar(tooltip, ancoraEm(q.left + x, q.top + y));
  }

  function destacar(id: string | null): void {
    const fonte = idFonte(nivel);
    const f = opcoes.fontes[nivel];
    if (!f || !adicionadas.has(nivel)) return;
    const sl = f.tipo === "pmtiles" ? { sourceLayer: f.camadaFonte } : {};
    if (destacado !== null) mapa.setFeatureState({ source: fonte, ...sl, id: destacado }, { destaque: false });
    destacado = id;
    if (id !== null) mapa.setFeatureState({ source: fonte, ...sl, id }, { destaque: true });
  }

  function esconderTooltip(): void {
    tooltip.hidden = true;
    destacar(null);
  }

  const ouvintesMapa: (() => void)[] = [];
  function ligarInteracao(n: Nivel, f: FonteGeometria): void {
    const aoMover = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }): void => {
      if (n !== nivel) return;
      const id = e.features?.[0]?.properties[f.idPropriedade] as string | number | undefined;
      if (id === undefined) return;
      // Mesmo id: só segue o cursor, sem refazer DOM do tooltip nem feature-state.
      if (String(id) === destacado) { posicionarTooltip(e.point.x, e.point.y); return; }
      destacar(String(id));
      mostrarTooltip(String(id), e.point.x, e.point.y);
    };
    const aoSair = (): void => { esconderTooltip(); };
    mapa.on("mousemove", idFill(n), aoMover);
    mapa.on("mouseleave", idFill(n), aoSair);
    const aoClicar = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }): void => {
      if (n !== nivel) return;
      const id = e.features?.[0]?.properties[f.idPropriedade] as string | number | undefined;
      if (id !== undefined) opcoes.aoSelecionar?.(String(id), n);
    };
    mapa.on("click", idFill(n), aoClicar);
    ouvintesMapa.push(() => { mapa.off("mousemove", idFill(n), aoMover); mapa.off("mouseleave", idFill(n), aoSair); mapa.off("click", idFill(n), aoClicar); });
  }

  // Teclado: setas percorrem as áreas com valor, na ordem do nome.
  let posicao = -1;
  const aoTeclar = (e: KeyboardEvent): void => {
    const ids = ordenados(nivel);
    if (ids.length === 0) return;
    if (e.key === "Escape") { posicao = -1; esconderTooltip(); return; }
    if ((e.key === "Enter" || e.key === " ") && destacado !== null) {
      e.preventDefault();
      opcoes.aoSelecionar?.(destacado, nivel);
      return;
    }
    const passo = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    const salto = e.key === "Home" ? 0 : e.key === "End" ? ids.length - 1 : null;
    if (passo === 0 && salto === null) return;
    e.preventDefault();
    posicao = salto ?? (posicao + passo + ids.length) % ids.length;
    const id = ids[posicao];
    if (id === undefined) return;
    destacar(id);
    mostrarTooltip(id, 8, 8);
  };
  quadro.addEventListener("keydown", aoTeclar);
  // focusout (borbulha) em vez de blur; ignora a troca de foco entre filhos do próprio quadro.
  const aoSairFoco = (e: FocusEvent): void => {
    if (e.relatedTarget instanceof Node && quadro.contains(e.relatedTarget)) return;
    esconderTooltip();
  };
  quadro.addEventListener("focusout", aoSairFoco);

  function preencherTabela(n: Nivel, valores: Readonly<Record<string, number>>, meta: MetaIndicador, detalhes?: Readonly<Record<string, DetalheParcial>>): void {
    const resumo = document.createElement("summary");
    resumo.textContent = `Tabela de valores: ${meta.nome}`;
    const t = document.createElement("table");
    const cap = document.createElement("caption");
    cap.textContent = `${meta.nome} (${meta.unidade}); denominador: ${meta.denominador}`;
    const cab = document.createElement("tr");
    for (const h of ["Área", "Taxa", "Votos", "Eleitorado", "Estimativa"]) { const th = document.createElement("th"); th.scope = "col"; th.textContent = h; cab.append(th); }
    const corpo = ordenados(n).map((id) => {
      const d = detalhes?.[id];
      const tr = document.createElement("tr");
      const c = textoTooltip({ nome: nomeDe(n, id), ...(d?.votos === undefined ? {} : { votos: d.votos }), taxa: valores[id] ?? 0, ...(d?.eleitorado === undefined ? {} : { eleitorado: d.eleitorado }) }, { unidade: meta.unidade, formatarTaxa });
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = c.titulo;
      const celulas = [...c.linhas.map(([, v]) => v), d?.nBaixo === true ? "instável (n baixo)" : "ok"];
      tr.append(th, ...celulas.map((v) => { const td = document.createElement("td"); td.textContent = v; return td; }));
      return tr;
    });
    t.append(cap, cab, ...corpo);
    tabela.replaceChildren(resumo, t);
  }

  // A tabela (~28 mil nós com 5.570 municípios) só é montada quando o <details> é aberto.
  let tabelaPendente: (() => void) | null = null;
  tabela.addEventListener("toggle", () => {
    if (tabela.open && tabelaPendente) { const f = tabelaPendente; tabelaPendente = null; f(); }
  });

  /** Enquadra a(s) UF(s) dos ids com valor pela tabela estática: determinístico, não depende de tiles já renderizados. */
  function enquadrarValores(ids: ReadonlySet<string>): void {
    const caixa = limitesDosIds(ids);
    if (caixa) mapa.fitBounds(caixa, { padding: 24, duration: 0 });
  }

  /** MapLibre não lê var(): resolve o token `--cor-sem-dado` do tema vigente a cada aplicação. */
  const corDoPreenchimento = (escala: Escala): ExpressionSpecification =>
    expressaoCor({ ...escala, corSemDado: cssVar("--cor-sem-dado", escala.corSemDado) }) as ExpressionSpecification;
  const escalaAtual = new Map<Nivel, Escala>();
  const temaEscuro = window.matchMedia("(prefers-color-scheme: dark)");
  /** Troca de tema do sistema: repinta fundo e áreas sem dado sem recarregar geometria. */
  const aoTrocarTema = (): void => {
    if (!mapa.getLayer("fundo")) return;
    mapa.setPaintProperty("fundo", "background-color", cssVar("--cor-superficie", "#f4f6f8"));
    for (const n of adicionadas) {
      const e = escalaAtual.get(n);
      mapa.setPaintProperty(idFill(n), "fill-color", e ? corDoPreenchimento(e) : cssVar("--cor-sem-dado", "#c3c9d0"));
    }
  };
  temaEscuro.addEventListener("change", aoTrocarTema);
  // Alternância manual de tema (botão do cabeçalho) avisa por evento: MapLibre não lê var().
  window.addEventListener("tema-alterado", aoTrocarTema);

  function aplicarValores(n: Nivel, valores: Readonly<Record<string, number>>, escala: Escala, detalhes?: Readonly<Record<string, DetalheParcial>>): void {
    const f = garantirNivel(n);
    const fonte = idFonte(n);
    const sl = f.tipo === "pmtiles" ? { sourceLayer: f.camadaFonte } : {};
    mapa.removeFeatureState({ source: fonte, ...sl });
    for (const [id, valor] of Object.entries(valores)) mapa.setFeatureState({ source: fonte, ...sl, id }, { valor, nbaixo: detalhes?.[id]?.nBaixo === true });
    escalaAtual.set(n, escala);
    mapa.setPaintProperty(idFill(n), "fill-color", corDoPreenchimento(escala));
    destacado = null;
    stats.atualizacoesDeValores += 1;
  }

  const api: Mapa = {
    pronto,
    definirValores(valores, escala, meta, detalhes) {
      validarCoropletico(meta);
      const legenda = criarLegenda(escala, meta, meta.tipo === "taxa" ? { formatar: formatarTaxa } : {});
      const finitos = soFinitos(valores);
      valoresPorNivel.set(nivel, finitos);
      idsOrdenados.delete(nivel);
      if (detalhes) detalhesPorNivel.set(nivel, { ...detalhes });
      metaAtual = meta;
      const n = nivel;
      quandoPronto(() => { aplicarValores(n, finitos, escala, detalhes); if (opcoes.fontes[n]?.tipo === "pmtiles") enquadrarValores(new Set(Object.keys(finitos))); });
      areaLegenda.replaceChildren(legenda, legendaHachura());
      const resumo = document.createElement("summary");
      resumo.textContent = `Tabela de valores: ${meta.nome}`;
      tabela.replaceChildren(resumo);
      const nTabela = nivel;
      tabelaPendente = () => { preencherTabela(nTabela, finitos, meta, detalhes); };
      if (tabela.open) { const f = tabelaPendente; tabelaPendente = null; f(); }
    },
    definirAbrangencia(codigoUf, limites) {
      abrangenciaUf = codigoUf;
      quandoPronto(() => {
        for (const n of adicionadas) {
          const f = opcoes.fontes[n];
          if (!f) continue;
          mapa.setPaintProperty(idFill(n), "fill-opacity", opacidadeFill(f.idPropriedade));
          mapa.setPaintProperty(idLinha(n), "line-opacity", opacidadeLinha(f.idPropriedade));
        }
        mapa.fitBounds(limites ?? limitesIniciais(opcoes.fontes[nivel] ?? opcoes.fontes.municipio), { padding: 24, duration: 0 });
      });
    },
    definirNivel(novo) {
      if (!opcoes.fontes[novo]) throw new Error(`Nível "${novo}" sem fonte de geometria configurada.`);
      esconderTooltip();
      const anterior = nivel;
      nivel = novo;
      quandoPronto(() => {
        garantirNivel(novo);
        for (const n of adicionadas) {
          const v = n === novo ? "visible" : "none";
          mapa.setLayoutProperty(idFill(n), "visibility", v);
          mapa.setLayoutProperty(idHachura(n), "visibility", v);
          mapa.setLayoutProperty(idLinha(n), "visibility", v);
        }
        if (anterior !== novo) mapa.fitBounds(limitesIniciais(opcoes.fontes[novo] as FonteGeometria), { padding: 24, duration: 0 });
      });
    },
    definirPontos(pontos) {
      const votosMax = Math.max(1, ...pontos.features.map((x) => Number(x.properties?.["votos"] ?? 0)));
      quandoPronto(() => {
        const existente = mapa.getSource<GeoJSONSource>("locais");
        if (existente) void existente.setData(pontos);
        else mapa.addSource("locais", { type: "geojson", data: pontos });
        for (const id of ["pontos-circulo", "pontos-calor"]) if (mapa.getLayer(id)) mapa.removeLayer(id);
        // Azul do lado "acima" da divergente: destaca-se do coroplético amarelo/âmbar sem usar a mesma escala.
        const rampa = PALETAS.divergente;
        mapa.addLayer({
          id: "pontos-calor", type: "heatmap", source: "locais", maxzoom: 10,
          paint: {
            "heatmap-weight": expressaoPesoCalor(votosMax) as ExpressionSpecification,
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 5, 12, 10, 30],
            "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.85, 10, 0],
            "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(31,83,133,0)", 0.2, rampa[6], 0.45, rampa[5], 0.75, rampa[4], 1, "#ffffff"],
          },
        });
        mapa.addLayer({
          id: "pontos-circulo", type: "circle", source: "locais", minzoom: 8,
          paint: {
            "circle-radius": expressaoRaioCirculo(votosMax, 18) as ExpressionSpecification,
            "circle-color": rampa[5], "circle-opacity": 0.8, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1,
          },
        });
      });
    },
    estatisticas: () => ({ ...stats }),
    destruir() {
      quadro.removeEventListener("keydown", aoTeclar);
      quadro.removeEventListener("focusout", aoSairFoco);
      mapa.off("idle", aoOciosoColherNomes);
      ouvintesMapa.splice(0).forEach((f) => { f(); });
      fila.length = 0;
      temaEscuro.removeEventListener("change", aoTrocarTema);
      window.removeEventListener("tema-alterado", aoTrocarTema);
      mapa.remove();
      container.replaceChildren();
    },
  };
  quandoPronto(() => { garantirNivel(nivel); });
  return api;
}

function limitesIniciais(f: FonteGeometria): Limites {
  return f.tipo === "geojson" ? limitesDe(f.dados) : f.limites;
}
