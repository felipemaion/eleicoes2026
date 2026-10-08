/**
 * Fronteira com o MapLibre: único ponto que baixa o WebGL (import dinâmico) e que conhece a
 * geometria. Com tiles publicados (`/tiles/manifesto.json`) usa PMTiles de todas as UFs; sem
 * eles (404, p.ex. dev sem ETL) cai na fixture de Sergipe — e as telas avisam, via `geometria()`.
 */
import type { FeatureCollection } from "geojson";
import type { Mapa, Nivel, OpcoesMapa } from "../componentes/mapa/mapa";
import { carregarManifesto, fontesDoManifesto, type ManifestoTiles } from "../dados/tiles";
import urlMunicipios from "../../tests/fixtures/se-municipios.geojson?url";

export type Geometria = "pmtiles" | "demonstracao";

/** Única UF com geometria na demonstração (sem tiles). */
export const UF_DA_DEMONSTRACAO = "SE";

let manifesto: Promise<ManifestoTiles | null> | null = null;
function obterManifesto(): Promise<ManifestoTiles | null> {
  // Falha não fica em cache: a próxima tela tenta de novo.
  manifesto ??= carregarManifesto().catch((e: unknown) => { manifesto = null; throw e; });
  return manifesto;
}

export async function geometria(): Promise<Geometria> {
  return (await obterManifesto()) === null ? "demonstracao" : "pmtiles";
}

export interface OpcoesEmbutido extends Pick<OpcoesMapa, "formatarTaxa" | "aoSelecionar"> {
  /** Ano da eleição: escolhe a camada `zonas_<ano>`. */
  ano?: number;
}

async function buscarGeo(url: string): Promise<FeatureCollection> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} falhou: ${String(r.status)}`);
  return (await r.json()) as FeatureCollection;
}

/** Níveis que a geometria disponível permite (zona só com PMTiles do ano). */
export async function niveisDisponiveis(ano: number): Promise<Nivel[]> {
  const m = await obterManifesto();
  return m !== null && `zonas_${String(ano)}` in m.camadas ? ["municipio", "zona"] : ["municipio"];
}

export async function montarMapa(area: HTMLElement, rotuloAcessivel: string, o: OpcoesEmbutido = {}): Promise<Mapa> {
  const [m, { criarMapa }] = await Promise.all([obterManifesto(), import("../componentes/mapa/mapa")]);
  const fontes = m === null
    ? { municipio: { tipo: "geojson" as const, dados: await buscarGeo(urlMunicipios), idPropriedade: "cd_mun_ibge" } }
    : fontesDoManifesto(m, o.ano ?? 2026, window.location.origin);
  return criarMapa(area, {
    fontes, rotuloAcessivel,
    ...(o.formatarTaxa ? { formatarTaxa: o.formatarTaxa } : {}),
    ...(o.aoSelecionar ? { aoSelecionar: o.aoSelecionar } : {}),
  });
}
