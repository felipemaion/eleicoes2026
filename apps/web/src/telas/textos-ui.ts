/** Textos públicos em DOM: "?" de ajuda, avisos, subtítulo e rodapé de cada tela. */
import type { Fonte, FonteRede } from "../dados/contrato";
import { avisosDaTela, formatarDtGeracao, indicadorDe, notaRodape, subtituloDaTela, type Contexto, type ContextoAvisos, type TelaComTextos } from "../textos";
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

/**
 * Avisos obrigatórios da tela, compactos: o mais importante (1º de nível "atencao", senão o 1º) fica
 * à vista e o restante recolhe em "Notas sobre os dados (N)". `null` quando nenhum se aplica.
 */
export function avisosUi(tela: TelaComTextos, ctx: ContextoAvisos): HTMLElement | null {
  const lista = avisosDaTela(tela, ctx);
  if (lista.length === 0) return null;
  const essencial = lista.find((a) => a.nivel === "atencao") ?? lista[0];
  const resto = lista.filter((a) => a !== essencial);
  const linha = (a: (typeof lista)[number]): HTMLElement => {
    const p = h("p", {}, h("strong", { textContent: `${a.titulo}. ` }), a.texto);
    p.dataset["nivel"] = a.nivel;
    return p;
  };
  const aside = h("aside", { className: "avisos" }, ...(essencial ? [linha(essencial)] : []));
  if (resto.length > 0) aside.append(h("details", { className: "avisos-resto" }, h("summary", { textContent: `Notas sobre os dados (${String(resto.length)})` }), ...resto.map(linha)));
  aside.setAttribute("aria-label", "Avisos de leitura");
  return aside;
}

export const cabecalhoDaTela = (tela: TelaComTextos): HTMLElement => h("p", { className: "subtitulo", textContent: subtituloDaTela(tela) });
export const rodapeUi = (tela: TelaComTextos, ctx: Contexto): HTMLElement => nota(notaRodape(tela, ctx));

/**
 * "fonte" discreto ao lado de um número: dataset, data de geração do TSE, regra aplicada e links
 * (arquivo oficial + metodologia). `datasets` escolhe quais fontes da resposta valem para o número.
 * Sem fonte correspondente o texto diz isso, em vez de omitir a procedência.
 */
export function fonteUi(fontes: readonly Fonte[], datasets: readonly string[]): HTMLElement {
  const usadas = fontes.filter((f) => datasets.includes(f.dataset));
  if (usadas.length === 0) return h("span", { className: "fonte fonte-ausente", textContent: "fonte não informada" });
  const id = `fonte-${String(++contador)}`;
  const painel = h("div", { id, hidden: true, className: "fonte-painel" },
    ...usadas.map((f) => h("div", { className: "fonte-item" },
      h("strong", { textContent: f.dataset }),
      h("dl", {},
        h("dt", { textContent: "Gerado pelo TSE em" }), h("dd", { textContent: formatarDtGeracao(f.dt_geracao) }),
        h("dt", { textContent: "Regra" }), h("dd", { textContent: f.coluna_regra }),
      ),
      h("p", {},
        h("a", { href: f.arquivo_oficial_url, target: "_blank", rel: "noopener noreferrer", textContent: "Arquivo oficial" }), " · ",
        h("a", { href: f.metodologia_url, target: "_blank", rel: "noopener noreferrer", textContent: "Metodologia" }),
      ),
    )),
  );
  const botao = h("button", { type: "button", className: "fonte-botao", textContent: "fonte" });
  botao.setAttribute("aria-label", `Fonte dos dados: ${usadas.map((f) => f.dataset).join(", ")}`);
  botao.setAttribute("aria-expanded", "false");
  botao.setAttribute("aria-controls", id);
  const raiz = h("span", { className: "fonte" }, botao, painel);
  ligarPainel(raiz, botao, painel);
  return raiz;
}

/**
 * "fonte" para números que não vêm do TSE (Instagram): mostra a frase de procedência pronta da API
 * (`rotulo`, ex.: "Instagram — API oficial da Meta, coletado em 08/10/2026"), a regra e os links.
 */
export function fonteRotuladaUi(fontes: readonly FonteRede[], datasets: readonly string[]): HTMLElement {
  const usadas = fontes.filter((f) => datasets.includes(f.dataset));
  if (usadas.length === 0) return h("span", { className: "fonte fonte-ausente", textContent: "fonte não informada" });
  const id = `fonte-${String(++contador)}`;
  const painel = h("div", { id, hidden: true, className: "fonte-painel" },
    ...usadas.map((f) => h("div", { className: "fonte-item" },
      h("strong", { textContent: f.rotulo }),
      h("dl", {}, h("dt", { textContent: "Regra" }), h("dd", { textContent: f.coluna_regra })),
      h("p", {},
        h("a", { href: f.arquivo_oficial_url, target: "_blank", rel: "noopener noreferrer", textContent: "Fonte oficial" }), " · ",
        h("a", { href: f.metodologia_url, target: "_blank", rel: "noopener noreferrer", textContent: "Metodologia" }),
      ),
    )),
  );
  const botao = h("button", { type: "button", className: "fonte-botao", textContent: "fonte" });
  botao.setAttribute("aria-label", `Fonte dos dados: ${usadas.map((f) => f.rotulo).join("; ")}`);
  botao.setAttribute("aria-expanded", "false");
  botao.setAttribute("aria-controls", id);
  const raiz = h("span", { className: "fonte" }, botao, painel);
  ligarPainel(raiz, botao, painel);
  return raiz;
}
