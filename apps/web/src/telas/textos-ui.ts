/** Textos públicos em DOM: "?" de ajuda, avisos, subtítulo e rodapé de cada tela. */
import { avisosDaTela, indicadorDe, notaRodape, subtituloDaTela, type Contexto, type ContextoAvisos, type TelaComTextos } from "../textos";
import { ligarPainel } from "../componentes/ui/tooltip";
import { h, nota } from "./dom";

let contador = 0;

/** Botão "?" que abre um painel com o texto público do indicador (hover/foco abrem, clique fixa, Esc fecha). */
export function ajuda(chave: string, ctx: Contexto): HTMLElement {
  const i = indicadorDe(chave, ctx);
  const id = `ajuda-${String(++contador)}`;
  const painel = h("div", { id, hidden: true, className: "ajuda-painel" },
    h("p", { textContent: i.como_ler }),
    h("dl", {},
      h("dt", { textContent: "Unidade" }), h("dd", { textContent: i.unidade }),
      h("dt", { textContent: "Denominador" }), h("dd", { textContent: i.denominador }),
      h("dt", { textContent: "Cuidado" }), h("dd", { textContent: i.cuidado }),
      h("dt", { textContent: "Fonte" }), h("dd", { textContent: i.fonte }),
    ),
  );
  const botao = h("button", { type: "button", className: "ajuda-botao", textContent: "?" });
  botao.setAttribute("aria-label", `Ajuda: ${i.titulo}`);
  botao.setAttribute("aria-expanded", "false");
  botao.setAttribute("aria-controls", id);
  const raiz = h("span", { className: "ajuda" }, botao, painel);
  ligarPainel(raiz, botao, painel);
  return raiz;
}

/** Avisos obrigatórios da tela; `null` quando nenhum se aplica (sem região vazia para leitores de tela). */
export function avisosUi(tela: TelaComTextos, ctx: ContextoAvisos): HTMLElement | null {
  const lista = avisosDaTela(tela, ctx);
  if (lista.length === 0) return null;
  const aside = h("aside", { className: "avisos" },
    ...lista.map((a) => {
      const p = h("p", {}, h("strong", { textContent: `${a.titulo}. ` }), a.texto);
      p.dataset["nivel"] = a.nivel;
      return p;
    }),
  );
  aside.setAttribute("aria-label", "Avisos de leitura");
  return aside;
}

export const cabecalhoDaTela = (tela: TelaComTextos): HTMLElement => h("p", { className: "subtitulo", textContent: subtituloDaTela(tela) });
export const rodapeUi = (tela: TelaComTextos, ctx: Contexto): HTMLElement => nota(notaRodape(tela, ctx));
