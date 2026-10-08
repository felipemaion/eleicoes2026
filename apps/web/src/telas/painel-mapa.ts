/** Mapa + dados da API: monta uma vez, recolore a cada `atualizar` sem recarregar a geometria. */
import type { FeatureCollection } from "geojson";
import { escalaDoMapa } from "../dados/adaptadores";
import type { ClienteApi, Params } from "../dados/cliente";
import type { PontoVoto, RespostaMapa } from "../dados/contrato";
import { montarMapa } from "./mapa-embutido";

/** Única UF com geometria até os PMTiles (T-D04). */
export const UF_COM_GEOMETRIA = "SE";

export interface PainelMapa {
  /** Resolve com a resposta aplicada; `null` se uma chamada mais nova a substituiu. */
  atualizar(params: Params): Promise<RespostaMapa | null>;
  /** Símbolos proporcionais (absolutos) por local de votação. */
  mostrarPontos(params: Params | null): Promise<void>;
  destruir(): void;
}

export function paraGeoJson(pontos: readonly PontoVoto[]): FeatureCollection {
  return { type: "FeatureCollection", features: pontos.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: { votos: p.votos } })) };
}

export function criarPainelMapa(area: HTMLElement, cliente: ClienteApi, rotulo: string): PainelMapa {
  const mapa = montarMapa(area, rotulo);
  let destruido = false;
  let seq = 0;
  // Sem isto, falha ao montar o mapa viraria "unhandled rejection" antes de alguém aguardar.
  mapa.catch(() => { /* o erro chega a quem chamar atualizar() */ });
  return {
    async atualizar(params) {
      const minha = ++seq;
      const [m, resposta] = await Promise.all([mapa, cliente.mapa(params)]);
      if (destruido || minha !== seq) return null;
      const { escala, meta, valores, detalhes } = escalaDoMapa(resposta);
      m.definirValores(valores, escala, meta, detalhes);
      return resposta;
    },
    async mostrarPontos(params) {
      const m = await mapa;
      if (params === null) { m.definirPontos(paraGeoJson([])); return; }
      const { pontos } = await cliente.pontos(params);
      if (!destruido) m.definirPontos(paraGeoJson(pontos));
    },
    destruir() {
      destruido = true;
      void mapa.then((m) => { m.destruir(); }, () => { /* nunca montou */ });
    },
  };
}
