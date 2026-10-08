import type { FeatureCollection } from "geojson";
import { escalaDivergente, escalaLog, escalaQuantil, type Escala, type MetaIndicador } from "../componentes/escalas/escalas";
import type { DetalheLocal } from "../componentes/mapa/tooltip";
import urlLocais from "../../tests/fixtures/se-locais.geojson?url";
import urlMunicipios from "../../tests/fixtures/se-municipios.geojson?url";
import urlValores from "../../tests/fixtures/se-valores.json?url";
import type { Tela } from "./tipos";

// MapLibre entra por import() dinâmico: só quem abre o mapa baixa o WebGL.
// Enquanto a API/PMTiles (T-D04) não existem, esta tela usa a fixture de Sergipe.
interface LinhaFixture { eleitorado: number; votos: number; taxa: number; swing: number; lq: number }

interface Indicador {
  rotulo: string;
  meta: MetaIndicador;
  valor: (l: LinhaFixture) => number;
  escala: (v: number[]) => Escala;
}

const INDICADORES: Readonly<Record<string, Indicador>> = {
  penetracao: {
    rotulo: "Penetração",
    meta: { nome: "Penetração", tipo: "taxa", unidade: "% dos votos válidos", denominador: "votos válidos do município" },
    valor: (l) => l.taxa,
    escala: (v) => escalaQuantil(v),
  },
  swing: {
    rotulo: "Swing 2022→2026",
    meta: { nome: "Swing", tipo: "diferenca", unidade: "diferença da fração de votos válidos", denominador: "votos válidos do município" },
    valor: (l) => l.swing,
    escala: () => escalaDivergente({ extensao: 0.04 }),
  },
  lq: {
    rotulo: "Quociente locacional (LQ)",
    meta: { nome: "Quociente locacional", tipo: "razao", unidade: "razão (1 = média do estado)", denominador: "participação do município nos votos do estado ÷ no eleitorado do estado" },
    valor: (l) => l.lq,
    escala: () => escalaLog({ fatorMaximo: 4 }),
  },
};

async function buscar<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} falhou: ${String(r.status)}`);
  return (await r.json()) as T;
}

export const tela: Tela = {
  titulo: "Mapa",
  render(container) {
    const h1 = document.createElement("h1");
    h1.textContent = "Mapa";
    h1.tabIndex = -1;
    const aviso = document.createElement("p");
    aviso.textContent = "Dados de demonstração (fixture de Sergipe) até a API ficar pronta.";
    const label = document.createElement("label");
    label.textContent = "Indicador";
    const select = document.createElement("select");
    for (const [chave, i] of Object.entries(INDICADORES)) select.add(new Option(i.rotulo, chave));
    label.append(select);
    const area = document.createElement("div");
    area.className = "mapa-area";
    area.dataset["mapaPronto"] = "nao";
    container.replaceChildren(h1, aviso, label, area);

    let cancelado = false;
    let destruir = (): void => { /* ainda sem mapa */ };

    void Promise.all([buscar<FeatureCollection>(urlMunicipios), buscar<Record<string, LinhaFixture>>(urlValores), buscar<FeatureCollection>(urlLocais), import("../componentes/mapa/mapa")])
      .then(([geo, linhas, locais, { criarMapa }]) => {
        if (cancelado) return;
        const mapa = criarMapa(area, { fontes: { municipio: { tipo: "geojson", dados: geo, idPropriedade: "cd_mun_ibge" } }, rotuloAcessivel: "Mapa de municípios de Sergipe" });
        destruir = () => { mapa.destruir(); };
        const detalhes: Record<string, DetalheLocal> = {};
        const nomes = new Map(geo.features.map((f) => [String(f.properties?.["cd_mun_ibge"]), String(f.properties?.["nome"])]));
        for (const [id, l] of Object.entries(linhas)) detalhes[id] = { nome: nomes.get(id) ?? id, votos: l.votos, taxa: l.taxa, eleitorado: l.eleitorado };
        const atualizar = (): void => {
          const ind = INDICADORES[select.value];
          if (!ind) throw new Error(`Indicador desconhecido: ${select.value}`);
          const valores = Object.fromEntries(Object.entries(linhas).map(([id, l]) => [id, ind.valor(l)]));
          mapa.definirValores(valores, ind.escala(Object.values(valores)), ind.meta, detalhes);
          const e = mapa.estatisticas();
          area.dataset["fontes"] = String(e.fontesCarregadas);
          area.dataset["atualizacoes"] = String(e.atualizacoesDeValores);
        };
        select.addEventListener("change", atualizar);
        mapa.definirPontos(locais);
        atualizar();
        void mapa.pronto.then(() => {
          if (cancelado) return;
          const e = mapa.estatisticas();
          area.dataset["fontes"] = String(e.fontesCarregadas);
          area.dataset["atualizacoes"] = String(e.atualizacoesDeValores);
          area.dataset["mapaPronto"] = "sim";
        });
      })
      .catch((erro: unknown) => {
        aviso.textContent = `Não foi possível carregar o mapa: ${erro instanceof Error ? erro.message : String(erro)}`;
        aviso.setAttribute("role", "alert");
      });

    return () => {
      cancelado = true;
      destruir();
      container.replaceChildren();
    };
  },
};
