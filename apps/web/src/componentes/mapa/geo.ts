import type { FeatureCollection, Geometry, Position } from "geojson";

export type Limites = [oeste: number, sul: number, leste: number, norte: number];

function posicoes(g: Geometry): Position[] {
  switch (g.type) {
    case "Point": return [g.coordinates];
    case "MultiPoint":
    case "LineString": return g.coordinates;
    case "MultiLineString":
    case "Polygon": return g.coordinates.flat();
    case "MultiPolygon": return g.coordinates.flat(2);
    case "GeometryCollection": return g.geometries.flatMap(posicoes);
  }
}

/** Caixa envolvente [oeste, sul, leste, norte] de uma FeatureCollection. */
export function limitesDe(fc: FeatureCollection): Limites {
  const pts = fc.features.flatMap((f) => posicoes(f.geometry));
  if (pts.length === 0) throw new Error("limitesDe: geometria vazia.");
  const xs = pts.map((p) => p[0] ?? 0);
  const ys = pts.map((p) => p[1] ?? 0);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
