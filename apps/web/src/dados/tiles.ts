/**
 * Manifesto dos PMTiles (`/tiles/manifesto.json`, escrito pelo ETL). O arquivo tem hash no nome
 * (cache imutável); o manifesto não, então é sempre revalidado. Formato:
 *   { camadas: { municipios: {arquivo, camada, id, limites}, zonas_<ano>: {...} } }
 */
import type { FonteGeometria } from "../componentes/mapa/mapa";
import type { Limites } from "../componentes/mapa/geo";

export interface CamadaTiles {
  /** Nome com hash, relativo a `/tiles/`. */
  arquivo: string;
  /** Nome da camada vetorial dentro do PMTiles. */
  camada: string;
  /** Propriedade que casa com a chave dos valores da API (IBGE, IBGE-zona). */
  id: string;
  limites: Limites;
}

export interface ManifestoTiles {
  camadas: Readonly<Record<string, CamadaTiles>>;
}

const ehObjeto = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

function lerCamada(nome: string, x: unknown): CamadaTiles {
  if (!ehObjeto(x)) throw new Error(`manifesto de tiles: camada "${nome}" inválida`);
  const { arquivo, camada, id, limites } = x;
  if (typeof arquivo !== "string" || typeof camada !== "string" || typeof id !== "string") {
    throw new Error(`manifesto de tiles: camada "${nome}" sem arquivo/camada/id`);
  }
  if (!Array.isArray(limites) || limites.length !== 4 || !limites.every((v) => typeof v === "number" && Number.isFinite(v))) {
    throw new Error(`manifesto de tiles: camada "${nome}" com limites inválidos (esperado [oeste, sul, leste, norte])`);
  }
  return { arquivo, camada, id, limites: limites as Limites };
}

/** Valida o JSON do manifesto; falha alto em vez de montar mapa com camada faltando. */
export function lerManifesto(x: unknown): ManifestoTiles {
  if (!ehObjeto(x) || !ehObjeto(x["camadas"])) throw new Error("manifesto de tiles: sem objeto `camadas`");
  const camadas = Object.fromEntries(Object.entries(x["camadas"]).map(([n, c]) => [n, lerCamada(n, c)]));
  if (!("municipios" in camadas)) throw new Error("manifesto de tiles: falta a camada `municipios`");
  return { camadas };
}

/** Fontes do mapa para um ano: município sempre; zona só se existir `zonas_<ano>`. */
export function fontesDoManifesto(m: ManifestoTiles, ano: number, origem: string): Partial<Record<"zona", FonteGeometria>> & { municipio: FonteGeometria } {
  const fonte = (c: CamadaTiles): FonteGeometria => ({
    tipo: "pmtiles", url: `${origem}/tiles/${c.arquivo}`, camadaFonte: c.camada, idPropriedade: c.id, limites: c.limites,
  });
  const mun = m.camadas["municipios"];
  if (!mun) throw new Error("manifesto de tiles: falta a camada `municipios`");
  const zona = m.camadas[`zonas_${String(ano)}`];
  return { municipio: fonte(mun), ...(zona ? { zona: fonte(zona) } : {}) };
}

/** `null` = tiles ainda não publicados (404); qualquer outra falha é erro de verdade. */
export async function carregarManifesto(): Promise<ManifestoTiles | null> {
  const r = await fetch("/tiles/manifesto.json", { cache: "no-cache" });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`GET /tiles/manifesto.json falhou: ${String(r.status)}`);
  return lerManifesto(await r.json());
}
