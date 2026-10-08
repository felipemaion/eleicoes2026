/** Regras puras da busca global: destaque do trecho, texto da sugestão, deep-links e query. */
import { cargoDaApi } from "../../dados/adaptadores";
import type { CandidaturaBusca } from "../../dados/contrato";
import { formatarNumero } from "../../formato";
import { ROTULO_CARGO } from "../../filtros-logica";
import { CARGOS, FILTROS_PADRAO, UFS, type Cargo, type Filtros, type Tela, type Uf } from "../../store";
import { formatarHash } from "../../rotas";

export interface Trecho { texto: string; marca: boolean }

/** Minúsculas sem acento, preservando o comprimento (NFD só separa o acento; o filtro o remove). */
const simplificar = (s: string): string => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Parte `texto` em trechos marcados/não marcados pela consulta, sem diferenciar caixa nem acento. */
export function destacarTrecho(texto: string, consulta: string): Trecho[] {
  const q = simplificar(consulta.trim());
  if (q === "") return [{ texto, marca: false }];
  // Compara letra a letra: um caractere com acento decomposto ocupa 1 posição no original.
  const mapa = Array.from(texto).map((c) => simplificar(c));
  const plano = mapa.join("");
  const i = plano.indexOf(q);
  if (i < 0) return [{ texto, marca: false }];
  let ini = 0;
  let acumulado = 0;
  const letras = Array.from(texto);
  while (ini < letras.length && acumulado < i) { acumulado += mapa[ini]?.length ?? 0; ini += 1; }
  let fim = ini;
  let cobertos = 0;
  while (fim < letras.length && cobertos < q.length) { cobertos += mapa[fim]?.length ?? 0; fim += 1; }
  const parte = (a: number, b: number): string => letras.slice(a, b).join("");
  return [
    ...(ini > 0 ? [{ texto: parte(0, ini), marca: false }] : []),
    { texto: parte(ini, fim), marca: true },
    ...(fim < letras.length ? [{ texto: parte(fim, letras.length), marca: false }] : []),
  ];
}

const cargoDaChave = (c: string): Cargo | null => CARGOS.find((k) => cargoDaApi(k) === c) ?? null;
const rotuloCargo = (c: string): string => {
  const k = cargoDaChave(c);
  return k ? ROTULO_CARGO[k] : c.charAt(0) + c.slice(1).toLowerCase();
};

export function linhaDaSugestao(c: CandidaturaBusca): string {
  const uf = c.uf === "BR" ? "Brasil" : c.uf;
  const votos = `${formatarNumero(c.votos)} ${c.votos === 1 ? "voto" : "votos"}`;
  return `${String(c.ano)} · ${rotuloCargo(c.cargo)} · ${uf} · ${c.partido.sigla} (${String(c.partido.numero)}) · ${votos}`;
}

/** Deep-link para a ficha ou para o mapa já com o recorte da candidatura (cargo, UF, ano, candidato). */
export function hashDaCandidatura(c: CandidaturaBusca, destino: Extract<Tela, "candidato" | "mapa">): string {
  const uf = (UFS as readonly string[]).includes(c.uf) ? (c.uf as Uf) : "BR";
  const filtros: Filtros = {
    ...FILTROS_PADRAO,
    uf,
    cargo: cargoDaChave(c.cargo) ?? FILTROS_PADRAO.cargo,
    ano: c.ano === 2022 ? 2022 : 2026,
    grupo: c.ano === 2022 ? "mbl_2022" : "missao_2026",
    candidato: `${String(c.ano)}:${String(c.sq_candidato)}`,
  };
  return formatarHash(destino, filtros);
}

/** `restringir` = a pessoa pediu para buscar só dentro dos filtros atuais; por padrão a busca é global. */
export function paramsDaBusca(q: string, f: Pick<Filtros, "uf" | "cargo" | "ano">, restringir = false): Record<string, string> {
  const p: Record<string, string> = { q: q.trim(), limite: "8" };
  if (restringir) {
    if (f.uf !== "BR") p["uf"] = f.uf;
    p["cargo"] = cargoDaApi(f.cargo);
    p["ano"] = String(f.ano);
  }
  return p;
}
