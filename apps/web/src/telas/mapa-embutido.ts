/**
 * Fronteira com o MapLibre: único ponto que baixa o WebGL (import dinâmico) e que conhece a
 * geometria. Enquanto os PMTiles (T-D04) não existem, a geometria é a fixture de Sergipe —
 * por isso as telas avisam quando a UF não é SE.
 */
import type { FeatureCollection } from "geojson";
import type { Mapa } from "../componentes/mapa/mapa";
import urlMunicipios from "../../tests/fixtures/se-municipios.geojson?url";

async function buscarGeo(url: string): Promise<FeatureCollection> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} falhou: ${String(r.status)}`);
  return (await r.json()) as FeatureCollection;
}

export async function montarMapa(area: HTMLElement, rotuloAcessivel: string): Promise<Mapa> {
  const [geo, { criarMapa }] = await Promise.all([buscarGeo(urlMunicipios), import("../componentes/mapa/mapa")]);
  return criarMapa(area, { fontes: { municipio: { tipo: "geojson", dados: geo, idPropriedade: "cd_mun_ibge" } }, rotuloAcessivel });
}
