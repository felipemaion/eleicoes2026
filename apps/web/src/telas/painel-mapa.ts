/** Mapa + dados da API: monta uma vez, recolore a cada `atualizar` sem recarregar a geometria. */
import type { FeatureCollection } from "geojson";
import { escalaDoMapa } from "../dados/adaptadores";
import { formatadorDaUnidade } from "../formato";
import type { ClienteApi, Params } from "../dados/cliente";
import type { PontoVoto, RespostaMapa } from "../dados/contrato";
import type { Nivel } from "../componentes/mapa/mapa";
import { montarMapa, type OpcoesEmbutido } from "./mapa-embutido";

export interface PainelMapa {
  /** Resolve com a resposta aplicada; `null` se uma chamada mais nova a substituiu. */
  atualizar(params: Params): Promise<RespostaMapa | null>;
  /** Símbolos proporcionais (absolutos) por local de votação. */
  mostrarPontos(params: Params | null): Promise<void>;
  /** Troca o nível exibido (município/zona); depois, chame `atualizar` para colorir. */
  definirNivel(nivel: Nivel): Promise<void>;
  destruir(): void;
}

export function paraGeoJson(pontos: readonly PontoVoto[]): FeatureCollection {
  return { type: "FeatureCollection", features: pontos.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: { votos: p.votos } })) };
}

export function criarPainelMapa(area: HTMLElement, cliente: ClienteApi, rotulo: string, opcoes: OpcoesEmbutido = {}): PainelMapa {
  area.dataset["mapaPronto"] = "nao";
  // A unidade (‰ ou %) só é conhecida com a resposta; legenda e tooltip leem este valor na hora de desenhar.
  let unidade = "‰";
  const mapa = montarMapa(area, rotulo, { ...opcoes, formatarTaxa: (v) => formatadorDaUnidade(unidade)(v) });
  let destruido = false;
  let seq = 0;
  let seqPontos = 0;
  // Função para o TS não estreitar `destruido`, que muda durante os awaits.
  const estaDestruido = (): boolean => destruido;
  let ctrlMapa: AbortController | null = null;
  let ctrlPontos: AbortController | null = null;
  // Sem isto, falha ao montar o mapa viraria "unhandled rejection" antes de alguém aguardar.
  mapa.catch(() => { /* o erro chega a quem chamar atualizar() */ });
  return {
    async atualizar(params) {
      const minha = ++seq;
      ctrlMapa?.abort();
      const ctrl = (ctrlMapa = new AbortController());
      // Função (não expressão) para o TS não estreitar `destruido`: ele muda durante os awaits.
      const obsoleto = (): boolean => destruido || minha !== seq;
      const [m, resposta] = await Promise.all([mapa, cliente.mapa(params, ctrl.signal)]);
      if (obsoleto()) return null;
      const { escala, meta, valores, detalhes } = escalaDoMapa(resposta);
      unidade = resposta.unidade;
      m.definirValores(valores, escala, meta, detalhes);
      await m.pronto;
      if (obsoleto()) return null;
      // Ganchos de observação para os testes e2e (geometria carregou 1×; N recolorações).
      const e = m.estatisticas();
      area.dataset["fontes"] = String(e.fontesCarregadas);
      area.dataset["atualizacoes"] = String(e.atualizacoesDeValores);
      area.dataset["mapaPronto"] = "sim";
      return resposta;
    },
    async mostrarPontos(params) {
      // Mesma regra do mapa: só a chamada mais recente (inclusive "desligar") pode escrever.
      const minha = ++seqPontos;
      ctrlPontos?.abort();
      const m = await mapa;
      if (minha !== seqPontos || destruido) return;
      if (params === null) { m.definirPontos(paraGeoJson([])); return; }
      const ctrl = (ctrlPontos = new AbortController());
      const { pontos } = await cliente.pontos(params, ctrl.signal);
      if (minha === seqPontos && !estaDestruido()) m.definirPontos(paraGeoJson(pontos));
    },
    async definirNivel(nivel) {
      (await mapa).definirNivel(nivel);
    },
    destruir() {
      destruido = true;
      ctrlMapa?.abort();
      ctrlPontos?.abort();
      void mapa.then((m) => { m.destruir(); }, () => { /* nunca montou */ });
    },
  };
}
