/** Roteamento por hash: `#/<tela>?uf=SP&ano=2022`. Só grava na URL o que difere do padrão. */
import { ANOS, CARGOS, FILTROS_PADRAO, GRUPOS, TELAS, UFS, type Estado, type Filtros, type Store, type Tela } from "./store";

export interface Rota {
  tela: Tela;
  filtros: Filtros;
}

export const ROTULOS_TELA: Readonly<Record<Tela, string>> = {
  "visao-geral": "Visão geral",
  mapa: "Mapa",
  gastos: "Gastos",
  evolucao: "Evolução 2022×2026",
  candidato: "Candidato",
};

/** Só `ano:sq` com caracteres seguros: o valor vai parar no caminho da API. */
const CANDIDATO_VALIDO = /^\d{4}:[A-Za-z0-9_-]+$/;
const PARAM: Readonly<Record<keyof Filtros, string>> = { uf: "uf", cargo: "cargo", grupo: "grupo", ano: "ano", candidato: "cand" };

function escolher<T extends string | number>(validos: readonly T[], bruto: string | null, padrao: T): T {
  return validos.find((v) => String(v) === bruto) ?? padrao;
}

/** Hash vazio = rota padrão; hash que não começa com `#/` (âncora como `#principal`) não é rota → null. */
export function lerHash(hash: string): Rota | null {
  if (hash !== "" && hash !== "#" && !hash.startsWith("#/")) return null;
  const [caminho = "", consulta = ""] = hash.replace(/^#\/?/, "").split("?");
  const q = new URLSearchParams(consulta);
  return {
    tela: escolher(TELAS, caminho, "visao-geral"),
    filtros: {
      uf: escolher([...UFS, "BR"] as const, q.get("uf"), FILTROS_PADRAO.uf),
      cargo: escolher(CARGOS, q.get("cargo"), FILTROS_PADRAO.cargo),
      grupo: escolher(GRUPOS, q.get("grupo"), FILTROS_PADRAO.grupo),
      ano: escolher(ANOS, q.get("ano"), FILTROS_PADRAO.ano),
      candidato: CANDIDATO_VALIDO.test(q.get("cand") ?? "") ? (q.get("cand") ?? "") : FILTROS_PADRAO.candidato,
    },
  };
}

export function formatarHash(tela: Tela, filtros: Filtros): string {
  const q = new URLSearchParams();
  (Object.keys(filtros) as (keyof Filtros)[]).forEach((k) => {
    if (filtros[k] !== FILTROS_PADRAO[k]) q.set(PARAM[k], String(filtros[k]));
  });
  const s = q.toString();
  return `#/${tela}${s ? `?${s}` : ""}`;
}

/** Sincroniza store ↔ hash nos dois sentidos. Retorna função que desliga a ligação. */
export function ligarStoreAoHash(store: Store, janela: Window): () => void {
  const doHash = (): void => {
    const rota = lerHash(janela.location.hash);
    if (rota) store.definir(rota.filtros, rota.tela);
  };
  const paraHash = (e: Readonly<Estado>): void => {
    const novo = formatarHash(e.tela, e.filtros);
    // replaceState: mudar filtro não deve empilhar uma entrada de histórico por clique.
    if (janela.location.hash !== novo) janela.history.replaceState(null, "", novo);
  };
  doHash();
  const desassinar = store.assinar(paraHash);
  janela.addEventListener("hashchange", doHash);
  return () => {
    desassinar();
    janela.removeEventListener("hashchange", doHash);
  };
}
