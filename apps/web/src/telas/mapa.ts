import { paramsMapaDoCandidato, textoForaDoMapa } from "../dados/abrangencia";
import { paramsDeFiltros } from "../dados/adaptadores";
import { criarCliente, foiCancelada } from "../dados/cliente";
import type { Abrangencia, Ficha, IndicadorApi, RespostaMapa } from "../dados/contrato";
import { formatarHash } from "../rotas";
import { rotuloDaUf } from "../filtros-logica";
import type { Uf } from "../store";
import type { Nivel } from "../componentes/mapa/mapa";
import { campoSelect, h, nota, titulo } from "./dom";
import { seguirCandidato } from "./recorte";
import { iniciarCarga } from "../componentes/ui/sobreposicao";
import { mostrarErro } from "./estados";
import { geometria, niveisDisponiveis, UF_DA_DEMONSTRACAO } from "./mapa-embutido";
import { criarPainelMapa } from "./painel-mapa";
import { criarDivisoria } from "../componentes/ui/divisoria";
import { desenharMunicipio, focarPainel } from "./painel-municipio";
import { ajuda, avisosUi, cabecalhoDaTela, rodapeUi } from "./textos-ui";
import type { Tela } from "./tipos";

const INDICADORES: readonly { valor: IndicadorApi; texto: string }[] = [
  { valor: "penetracao", texto: "Penetração (‰ dos aptos)" },
  { valor: "pct_validos", texto: "% dos votos válidos" },
];

/** O município de uma chave do mapa: "2800308" (município) ou "2800308-12" (zona). */
export const municipioDaChave = (id: string): string => id.split("-")[0] ?? id;

export const tela: Tela = {
  titulo: "Mapa",
  render(container, { filtros }) {
    const cliente = criarCliente();
    let indicador: IndicadorApi = "penetracao";
    let ficha: Ficha | null = null;
    let nivelAtual: Nivel = "municipio";
    let densidade = false;
    let vivo = true;
    let seqAtualizar = 0;
    let seqMun = 0;
    let ctrlMun: AbortController | null = null;

    const status = h("div", { className: "estado" });
    const rodape = h("div");
    const area = h("div", { className: "mapa-area" });
    const painel = h("aside", { className: "painel-municipio" });
    painel.setAttribute("aria-live", "polite");
    painel.setAttribute("aria-label", "Resumo do município");
    painel.append(h("p", { textContent: "Clique em um município (ou use as setas e Enter com o mapa em foco) para ver o resumo." }));

    function selecionar(id: string): void {
      const ibge = municipioDaChave(id);
      ctrlMun?.abort();
      const ctrl = (ctrlMun = new AbortController());
      const minha = ++seqMun;
      const atual = (): boolean => vivo && minha === seqMun;
      cliente.municipio(ibge, ctrl.signal).then(
        (m) => { if (atual()) { desenharMunicipio(painel, m); focarPainel(painel); } },
        (e: unknown) => { if (atual() && !foiCancelada(e)) mostrarErro(painel, e, () => { selecionar(id); }); },
      );
    }

    const nivel = campoSelect("Nível", "nivel", [
      { valor: "municipio", texto: "Município" },
      { valor: "zona", texto: "Zona eleitoral", desabilitada: true },
      { valor: "h3", texto: "Hexágono H3 (em breve)", desabilitada: true },
    ], "municipio", (v) => {
      nivelAtual = v === "zona" ? "zona" : "municipio";
      void mapa.definirNivel(nivelAtual).then(atualizar);
    });
    const ind = campoSelect("Indicador", "indicador", INDICADORES, indicador, (v) => { indicador = v === "pct_validos" ? "pct_validos" : "penetracao"; mostrarAjuda(); void atualizar(); });
    const ajudaInd = h("span");
    const mostrarAjuda = (): void => { ajudaInd.replaceChildren(ajuda(indicador, {})); };
    mostrarAjuda();
    const cand = campoSelect("Candidato", "candidatoMapa", [{ valor: "", texto: "Grupo inteiro" }], filtros.candidato, (v) => {
      // O hash é a fonte de verdade: a rota atualiza o store e a tela se redesenha (deep-link grátis).
      window.location.hash = formatarHash("mapa", { ...filtros, candidato: v });
    });
    const foco = h("div", { className: "mapa-foco" });
    foco.hidden = true;
    const dens = h("input", { type: "checkbox", name: "densidade", checked: densidade });
    const avisoPontos = h("p", { className: "aviso-pontos" });
    avisoPontos.setAttribute("role", "status");
    dens.addEventListener("change", () => { densidade = dens.checked; void pontos(); });

    const avisos = h("div");
    const layout = h("div", { className: "mapa-layout" });
    // Largura do painel: padrão ≈ 24vw (18–30rem, como antes); o mapa nunca fica abaixo de 20rem.
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const divisoria = criarDivisoria({
      layout, chave: "eleicoes2026.mapa.painel", rotulo: "Largura do painel de detalhe",
      padrao: Math.min(30 * rem, Math.max(18 * rem, window.innerWidth * 0.24)), minPainel: 15 * rem, minMapa: 20 * rem,
    });
    layout.append(area, divisoria.elemento, painel);
    container.replaceChildren(
      titulo("Mapa"),
      cabecalhoDaTela("mapa"),
      avisos,
      foco,
      h("div", { className: "controles" }, ind.rotulo, ajudaInd, nivel.rotulo, cand.rotulo, h("label", {}, dens, " Densidade de votos (locais)")),
      status,
      avisoPontos,
      layout,
      // Avisos longos ficam abaixo do mapa: o mapa é o conteúdo principal e não deve sair da primeira tela.
      ...[avisosUi("mapa", {})].filter((x) => x !== null),
      rodape,
    );

    // Avisos que dependem da geometria disponível e habilitam o nível zona.
    void Promise.all([geometria(), niveisDisponiveis(filtros.ano)]).then(([g, niveis]) => {
      if (!vivo) return;
      if (g === "demonstracao" && filtros.uf !== UF_DA_DEMONSTRACAO) {
        avisos.append(nota(`Geometria de demonstração: os PMTiles do Brasil ainda não foram publicados e o mapa desenha apenas Sergipe (UF selecionada: ${filtros.uf}).`));
      }
      const zona = nivel.select.querySelector<HTMLOptionElement>("option[value=zona]");
      if (zona && niveis.includes("zona")) {
        if (filtros.uf === "BR") zona.textContent = "Zona eleitoral (escolha uma UF)";
        else zona.disabled = false;
      }
    }, (e: unknown) => { if (vivo) mostrarErro(status, e, () => { window.location.reload(); }); });

    const mapa = criarPainelMapa(area, cliente, `Mapa de ${filtros.uf === "BR" ? "municípios" : `municípios — ${filtros.uf}`}`, { ano: filtros.ano, aoSelecionar: (id) => { selecionar(id); } });
    // Com candidato, ano/cargo/UF vêm DELE (a ficha), nunca dos filtros da tela: presidente é o país todo.
    const parametros = (): Record<string, string | undefined> => ({
      ...(ficha ? paramsMapaDoCandidato(ficha.candidato) : paramsDeFiltros(filtros)), indicador, nivel: nivelAtual,
    });
    const abrangencia = (): Abrangencia => ficha?.candidato.abrangencia ?? (filtros.uf === "BR" ? { tipo: "pais", uf: null } : { tipo: "uf", uf: filtros.uf });

    function desenharFoco(): void {
      foco.hidden = ficha === null;
      if (!ficha) { foco.replaceChildren(); return; }
      const c = ficha.candidato;
      const a = c.abrangencia;
      const onde = a.tipo === "uf" && a.uf !== null ? rotuloDaUf(a.uf as Uf) : "Brasil inteiro";
      const sair = h("button", { type: "button", textContent: "Ver o grupo todo" });
      sair.addEventListener("click", () => { window.location.hash = formatarHash("mapa", { ...filtros, candidato: "" }); });
      foco.replaceChildren(h("p", {}, h("strong", { textContent: c.nm_urna }), ` — ${c.partido.sigla} · ${String(c.ano)}. Mostrando só onde disputou: ${onde}.`), sair);
    }

    async function pontos(): Promise<void> {
      try {
        // /mapa/pontos exige UF; no Brasil inteiro a densidade fica desligada, com aviso na tela.
        avisoPontos.textContent = "";
        const p = parametros();
        await mapa.mostrarPontos(densidade && p["uf"] !== undefined ? p : null);
        if (densidade && p["uf"] === undefined) avisoPontos.textContent = "A densidade por local de votação exige uma UF; escolha um estado ou um candidato estadual.";
      } catch (e) {
        // Cancelada = substituída por pedido mais novo. Falha real: o coroplético segue de pé,
        // só a densidade sai de cena, com aviso discreto (detalhe no console).
        if (vivo && !foiCancelada(e)) {
          console.error("Densidade de votos indisponível:", e);
          densidade = false;
          dens.checked = false;
          dens.disabled = true;
          avisoPontos.textContent = "Densidade de votos indisponível no momento. O mapa por município continua válido.";
          void mapa.mostrarPontos(null).catch(() => { /* já está desligada */ });
        }
      }
    }

    async function atualizar(): Promise<void> {
      const minha = ++seqAtualizar;
      status.replaceChildren();
      const fim = iniciarCarga("Carregando o mapa…");
      try {
        if (filtros.candidato && !ficha) {
          const [ano, sq] = filtros.candidato.split(":");
          ficha = await cliente.ficha(Number(ano), sq ?? "");
          if (!vivo || minha !== seqAtualizar) return;
          seguirCandidato(ficha.candidato);
          desenharFoco();
          if (!cand.select.querySelector(`option[value="${filtros.candidato}"]`)) cand.select.append(new Option(ficha.candidato.nm_urna, filtros.candidato));
          cand.select.value = filtros.candidato;
        }
        // Antes de colorir: o enquadramento tem de estar pronto quando `data-mapa-pronto` virar "sim".
        await mapa.definirAbrangencia(abrangencia());
        const r: RespostaMapa | null = await mapa.atualizar(parametros());
        if (!vivo || r === null || minha !== seqAtualizar) return;
        rodape.replaceChildren(rodapeUi("mapa", { dt_geracao: r.dt_geracao }));
        const fora = textoForaDoMapa(r.votos_fora_do_mapa);
        status.replaceChildren(...(r.escala_sugerida.aviso ? [nota(r.escala_sugerida.aviso)] : []), ...(fora ? [nota(fora)] : []));
        await pontos();
      } catch (e) {
        if (vivo && minha === seqAtualizar && !foiCancelada(e)) mostrarErro(status, e, () => { void atualizar(); });
      } finally {
        fim();
      }
    }

    cliente.candidatos({ ...paramsDeFiltros(filtros), limite: "500" }).then((r) => {
      if (!vivo) return;
      // O valor é `ano:sq`, o mesmo formato do hash (`cand=`), para a escolha virar deep-link.
      const existentes = new Set([...cand.select.options].map((o) => o.value));
      cand.select.append(...r.itens.map((c) => new Option(c.nm_urna, `${String(c.ano)}:${String(c.sq_candidato)}`)).filter((o) => !existentes.has(o.value)));
      cand.select.value = filtros.candidato;
    }, () => { /* a lista é opcional; o mapa do grupo funciona sem ela */ });

    void atualizar();
    return () => { vivo = false; divisoria.destruir(); ctrlMun?.abort(); mapa.destruir(); container.replaceChildren(); };
  },
};
