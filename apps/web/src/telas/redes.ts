import { cargoDaApi } from "../dados/adaptadores";
import { criarCliente, ErroApi, type ClienteApi } from "../dados/cliente";
import type { RedeCandidato, RespostaCorrelacoes, RespostaRedes } from "../dados/contrato";
import {
  buscarCandidatos, CARGOS_COM_SEGUNDO_TURNO, descreverStatus, detalheExcluidos, fraseResumo, interpretarCorrelacao, kpisDeRedes, paramsRedes,
  perfilAnalisado, pontosSeguidoresVotos, rankingsDeRedes, recorteDaTela, ritmoPorJanela, situacaoDaSerie, FONTE_INSTAGRAM, type Leitura,
} from "../dados/redes-logica";
import { formatarNumero, formatarPontos } from "../formato";
import { render as renderDispersao, type PontoCustoVoto } from "../componentes/graficos/dispersao";
import { render as renderKpi, type Kpi } from "../componentes/graficos/kpi";
import { render as renderRanking } from "../componentes/graficos/ranking";
import { render as renderRitmo } from "../componentes/graficos/ritmo";
import { render as renderSerie } from "../componentes/graficos/serie-tempo";
import { figuraCandidato } from "../componentes/ui/foto-candidato";
import { h, nota, titulo } from "./dom";
import { carregar } from "./estados";
import { ajuda, avisosUi, cabecalhoDaTela, fonteRotuladaUi, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

type Carga = { tipo: "ok"; redes: RespostaRedes; corr: RespostaCorrelacoes; rotuloGrupo: string } | { tipo: "indisponivel"; mensagem: string };
type Contexto = Parameters<typeof ajuda>[1];

const DS_INSTAGRAM = ["redes_perfis"];
const MSG_503 = "Os números de redes sociais ainda não foram publicados. Volte em instantes.";
const MSG_422 = "Redes sociais só existem para as candidaturas de 2026. Escolha o grupo do Partido Missão (2026).";

/** 503 (dado ainda não publicado) e 422 (grupo de outro ano) não são falha de rede: viram aviso, não "tente novamente". */
async function buscar(cliente: ClienteApi, params: Record<string, string>, grupo: string): Promise<Carga> {
  try {
    const [redes, corr, grupos] = await Promise.all([cliente.redes(params), cliente.redesCorrelacoes(params), cliente.grupos()]);
    return { tipo: "ok", redes, corr, rotuloGrupo: grupos.grupos.find((g) => g.id === grupo)?.rotulo ?? grupo };
  } catch (e) {
    if (e instanceof ErroApi && e.status === 503) return { tipo: "indisponivel", mensagem: MSG_503 };
    if (e instanceof ErroApi && e.status === 422) return { tipo: "indisponivel", mensagem: MSG_422 };
    throw e;
  }
}

function leitura(l: Leitura): HTMLElement {
  return h("div", { className: "leitura-correlacao" }, h("p", {}, h("strong", { textContent: l.resumo })), ...(l.detalhe === "" ? [] : [nota(l.detalhe)]));
}

const link = (href: string, texto: string): HTMLAnchorElement => h("a", { href, target: "_blank", rel: "noopener noreferrer", textContent: texto });

/** Cartão do candidato em foco: foto, status e links. Conta indisponível aparece como tal, com o motivo e o link do TSE. */
function cartaoDoFoco(c: RedeCandidato): HTMLElement {
  const perfil = perfilAnalisado(c);
  const links = h("p", { className: "foco-links" });
  for (const p of c.perfis) links.append(link(p.link, `@${p.username}`), " · ");
  links.append(link(c.link_tse_candidato.url, "Página no TSE"));
  const quando = c.tem_dados ? "" : perfil?.url_tse ? ` Endereço declarado ao TSE: ${perfil.url_tse}` : "";
  const corpo = h("div", {},
    h("strong", { className: "foco-nome", textContent: c.nm_urna }),
    h("p", { className: "nota", textContent: `${c.partido.sigla} (${String(c.partido.numero)}) · ${c.sg_uf} · ${c.votos === null ? "votos indisponíveis" : `${formatarNumero(c.votos)} votos`}` }),
    h("p", { className: c.tem_dados ? "foco-status" : "foco-status indisponivel", textContent: c.tem_dados ? `${descreverStatus(c)} — ${formatarNumero(c.seguidores ?? 0)} seguidores` : `Perfil indisponível. ${descreverStatus(c)}.${quando}` }),
    links,
  );
  return h("div", { className: "foco-cartao" }, figuraCandidato(c.nm_urna, c.foto_url, 60, 75), corpo);
}

function kpisDoFoco(c: RedeCandidato): Kpi[] {
  const k: Kpi[] = [];
  if (c.pct_video !== null) k.push({ fonte: FONTE_INSTAGRAM, rotulo: "Vídeos e reels", ajuda: "ritmo_posts", valor: c.pct_video, formato: "pontos", unidade: "% dos posts" });
  if (c.engajamento_medio !== null) k.push({ fonte: FONTE_INSTAGRAM, rotulo: "Engajamento médio por post", ajuda: "engajamento", valor: c.engajamento_medio, formato: "pontos", unidade: "% dos seguidores (campanha)" });
  if (c.engajamento_mediano !== null) k.push({ fonte: FONTE_INSTAGRAM, rotulo: "Engajamento mediano por post", ajuda: "engajamento", valor: c.engajamento_mediano, formato: "pontos", unidade: "% dos seguidores (campanha)" });
  if (c.variacao_ritmo_pct !== null) k.push({ fonte: FONTE_INSTAGRAM, rotulo: "Mudança de ritmo depois da eleição", ajuda: "ritmo_posts", valor: c.variacao_ritmo_pct, formato: "pontos", unidade: "% em posts por semana" });
  return k;
}

export const tela: Tela = {
  titulo: "Redes sociais",
  render(container, { filtros }) {
    const conteudo = h("div");
    container.replaceChildren(titulo("Redes sociais"), cabecalhoDaTela("redes"), conteudo);
    const cliente = criarCliente();
    const parar = carregar(
      conteudo,
      () => buscar(cliente, paramsRedes(filtros), filtros.grupo),
      (c) => (c.tipo === "indisponivel" ? c.mensagem : c.redes.candidatos.length === 0 ? "Nenhuma candidatura com Instagram declarado para estes filtros." : null),
      (c, destino) => {
        if (c.tipo !== "ok") return undefined;
        const { redes, corr, rotuloGrupo } = c;
        const ctx: Contexto & { avisos_redes: string[]; segundo_turno: boolean } = {
          dt_geracao: redes.dt_geracao, dt_coleta_redes: redes.coletado_em, avisos_redes: redes.avisos, segundo_turno: CARGOS_COM_SEGUNDO_TURNO.includes(filtros.cargo),
        };
        const fonte = (): Node => fonteRotuladaUi(redes.fontes, DS_INSTAGRAM);
        const destruir: (() => void)[] = [];
        let ativo = true;
        let aborto: AbortController | null = null;
        let foco: RedeCandidato | null = redes.candidatos.find((x) => x.tem_dados) ?? null;

        // ---- topo ----
        const kpis = h("div");
        const kp = renderKpi(kpis, kpisDeRedes(redes), { ajuda: (k) => ajuda(k, ctx), fonte });
        destruir.push(() => { kp.destruir(); });
        const exclusao = detalheExcluidos(redes.excluidos);

        // ---- dispersão ----
        const recorte = recorteDaTela(corr, cargoDaApi(filtros.cargo));
        const areaDispersao = h("div", { className: "grafico-redes-dispersao" });
        const pontosDisp: PontoCustoVoto[] = recorte === null ? [] : pontosSeguidoresVotos(recorte).map((p) => ({
          id: p.id, rotulo: p.rotulo, custo: p.seguidores, votos: p.votos, detalhe: p.detalhe, foto: p.foto, classe: p.classe,
          linkExterno: { url: p.linkPerfil, convite: "Clique para abrir o perfil no Instagram (nova aba)." },
        }));
        const disp = renderDispersao(areaDispersao, pontosDisp, {
          titulo: "Seguidores × votos por candidato", grandeza: "seguidores", formatoX: formatarNumero, rotuloEixoX: "Seguidores no Instagram (escala log)",
          ...(recorte?.ajuste ? { reta: { intercepto: recorte.ajuste.intercepto, inclinacao: recorte.ajuste.inclinacao, rotulo: "tendência do grupo" } } : {}),
          destaque: new Set(foco ? [String(foco.sq_candidato)] : []),
        });
        destruir.push(() => { disp.destruir(); });
        const pares = recorte?.pares ?? [];
        const parPrincipal = pares.find((p) => p.id === "seguidores_votos");
        const outrosPares = pares.filter((p) => p.id !== "seguidores_votos");
        const legenda = h("p", { className: "legenda-esperado" },
          h("span", { className: "chave acima", textContent: "voto acima do esperado (1,5× ou mais)" }), " ",
          h("span", { className: "chave neutro", textContent: "dentro do esperado" }), " ",
          h("span", { className: "chave abaixo", textContent: "abaixo do esperado (até 0,67×)" }),
        );

        // ---- candidato em foco: busca, ritmo e série ----
        const areaFoco = h("div", { className: "foco" });
        const areaRitmo = h("div", { className: "grafico-redes-ritmo" });
        const areaKpiFoco = h("div");
        const areaSerie = h("div", { className: "serie-seguidores" });
        let ritmo: ReturnType<typeof renderRitmo> | null = null;
        let kpiFoco: ReturnType<typeof renderKpi> | null = null;
        let serie: ReturnType<typeof renderSerie> | null = null;

        const desenharSerie = (): void => {
          aborto?.abort();
          serie?.destruir(); serie = null;
          if (foco === null) { areaSerie.replaceChildren(nota("Escolha um candidato na busca acima para ver a série de seguidores.")); return; }
          if (!foco.tem_dados) { areaSerie.replaceChildren(nota("Sem série: o perfil deste candidato está indisponível (veja o motivo acima).")); return; }
          const ctrl = (aborto = new AbortController());
          const alvo = foco;
          areaSerie.replaceChildren(nota("Carregando série…"));
          cliente.redesSerie({ sq: String(alvo.sq_candidato) }, ctrl.signal).then((s) => {
            if (!ativo || ctrl.signal.aborted) return;
            const idx = Math.max(0, s.series.findIndex((x) => x.username === perfilAnalisado(alvo)?.username));
            const sit = situacaoDaSerie(s, idx);
            if (sit.tipo === "um_ponto") {
              areaSerie.replaceChildren(
                h("p", { className: "serie-numero" }, h("strong", { textContent: formatarNumero(sit.seguidores) }), ` seguidores em `, link(sit.link, `@${sit.username}`)),
                nota(sit.nota),
              );
              return;
            }
            const grafico = h("div", { className: "grafico-redes-serie" });
            areaSerie.replaceChildren(h("p", { className: "serie-resumo" }, h("strong", { textContent: sit.resumo }), " em ", link(sit.link, `@${sit.username}`)), grafico, nota("A série começa na primeira coleta; antes dela o Instagram não informa o histórico."));
            serie = renderSerie(grafico, sit.pontos.map((p) => ({ quando: p.coletado_em, valor: p.seguidores })), { titulo: `Seguidores de @${sit.username}`, medida: "Seguidores" });
          }, (erro: unknown) => {
            if (!ativo || ctrl.signal.aborted) return;
            const semSerie = erro instanceof ErroApi && erro.status === 404;
            if (!semSerie) console.error("Série de seguidores indisponível:", erro);
            areaSerie.replaceChildren(nota(semSerie ? "Ainda não há série para este perfil." : "Não foi possível carregar a série agora."));
          });
        };

        const desenharFoco = (): void => {
          const itens: Node[] = foco === null ? [nota("Nenhum candidato com números neste recorte.")] : [cartaoDoFoco(foco)];
          areaFoco.replaceChildren(...itens);
          ritmo?.destruir(); ritmo = null;
          kpiFoco?.destruir(); kpiFoco = null;
          areaRitmo.replaceChildren();
          const janelas = ritmoPorJanela(redes, foco?.sq_candidato ?? null);
          ritmo = renderRitmo(areaRitmo, janelas, {
            titulo: "Posts por semana antes, durante e depois da campanha", rotuloGrupo: "Mediana do grupo",
            ...(foco?.tem_dados ? { nomeCandidato: foco.nm_urna } : {}),
          });
          const k = foco?.tem_dados ? kpisDoFoco(foco) : [];
          kpiFoco = renderKpi(areaKpiFoco, k, { ajuda: (x) => ajuda(x, ctx), fonte });
          disp.destacar(new Set(foco ? [String(foco.sq_candidato)] : []));
          desenharSerie();
        };

        // ---- busca ----
        const estadoBusca = h("p", { className: "nota" });
        estadoBusca.setAttribute("aria-live", "polite");
        const resultados = h("ul", { className: "busca-redes-resultados" });
        const campo = h("input", { type: "search", name: "busca-redes", placeholder: "Nome do candidato", maxLength: 80, autocomplete: "off" });
        campo.addEventListener("input", () => {
          const achados = buscarCandidatos(redes.candidatos, campo.value);
          resultados.replaceChildren(...achados.map((a) => {
            const b = h("button", { type: "button", textContent: a.nm_urna });
            b.append(h("span", { className: "nota", textContent: ` · ${a.sg_uf}${a.tem_dados ? "" : " · perfil indisponível"}` }));
            b.addEventListener("click", () => { foco = a; campo.value = a.nm_urna; resultados.replaceChildren(); estadoBusca.textContent = ""; desenharFoco(); });
            return h("li", {}, b);
          }));
          const q = campo.value.trim();
          estadoBusca.textContent = q.length < 2 ? "" : achados.length === 0 ? "Nenhum candidato com esse nome neste recorte." : `${String(achados.length)} ${achados.length === 1 ? "resultado" : "resultados"}.`;
        });
        const busca = h("label", {}, "Escolher candidato em foco", campo);

        // ---- ranking ----
        const rk = rankingsDeRedes(redes);
        const painelRanking = (rotulo: string, chave: string, dados: typeof rk.seguidores, formato: (v: number) => string, coluna: string): Node[] => {
          const area = h("div", { className: `ranking-redes ranking-${coluna}` });
          const g = renderRanking(area, dados, { titulo: rotulo, formato, colunaValor: coluna, topo: 10, largura: 460 });
          destruir.push(() => { g.destruir(); });
          return [h("h3", {}, rotulo, " ", ajuda(chave, ctx)), area];
        };

        destino.append(
          ...[avisosUi("redes", ctx)].filter((x) => x !== null),
          h("p", { className: "resumo-redes", textContent: fraseResumo(redes, rotuloGrupo, filtros) }),
          ...(exclusao === "" ? [] : [nota(`Fora dos números: ${exclusao}.`)]),
          kpis,
          h("h2", {}, "Seguidores × votos ", ajuda("seguidores_votos", ctx), fonte()),
          nota("Cada círculo é um candidato; clique para abrir o perfil dele no Instagram. Escala logarítmica nos dois eixos. A linha tracejada é a tendência do grupo: quem está acima dela teve mais votos do que o tamanho da conta faria esperar."),
          legenda, areaDispersao,
          ...(parPrincipal ? [h("h3", {}, "A relação, em palavras ", ajuda("correlacao_redes", ctx)), leitura(interpretarCorrelacao(parPrincipal))] : [nota("Sem recorte de correlação para este cargo e UF.")]),
          ...(outrosPares.length > 0 ? [h("details", { className: "outras-relacoes" }, h("summary", { textContent: "Engajamento e ritmo de posts também andam com o voto?" }), ...outrosPares.flatMap((p) => [h("h4", { textContent: p.rotulo }), leitura(interpretarCorrelacao(p))]))] : []),
          h("h2", {}, "Candidato em foco"),
          nota("Busque um candidato: o ritmo de posts e a série de seguidores abaixo mostram o dele. Candidaturas sem perfil público também aparecem, como indisponíveis."),
          h("div", { className: "controles" }, busca), estadoBusca, resultados, areaFoco,
          h("h2", {}, "Ritmo de posts: antes, durante e depois ", ajuda("ritmo_posts", ctx), fonte()),
          nota("Posts por semana em cada fase. “Depois da eleição” só tem taxa semanal quando já passaram 7 dias; até lá aparece n/d, que não é zero."),
          areaRitmo, areaKpiFoco,
          h("h2", {}, "Rankings"),
          nota("Só os 10 primeiros de cada lista; para achar alguém fora dela, use a busca."),
          h("div", { className: "rankings-redes" },
            ...painelRanking("Mais seguidores", "seguidores_votos", rk.seguidores, formatarNumero, "Seguidores"),
            ...painelRanking("Maior engajamento por post", "engajamento", rk.engajamento, (v) => formatarPontos(v), "Engajamento (%)"),
            ...painelRanking("Voto acima do esperado", "residuo_seguidores", rk.acimaDoEsperado, (v) => `${v.toFixed(1).replace(".", ",")}×`, "Votos ÷ esperado"),
          ),
          h("h2", {}, "Série de seguidores ", ajuda("serie_seguidores", ctx), fonte()),
          areaSerie,
          rodapeUi("redes", ctx),
        );
        desenharFoco();
        return () => {
          ativo = false;
          aborto?.abort();
          ritmo?.destruir(); kpiFoco?.destruir(); serie?.destruir();
          destruir.forEach((d) => { d(); });
        };
      },
    );
    return () => { parar(); container.replaceChildren(); };
  },
};
