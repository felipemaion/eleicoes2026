/**
 * Lógica pura da aba "Redes sociais": prepara o que os gráficos, o ranking e os textos mostram a partir de
 * `/api/redes`, `/api/redes/correlacoes` e `/api/redes/serie`. Sem DOM, sem rede.
 * Regra de ouro: conta sem números é "indisponível", nunca zero.
 */
import type { Barra } from "../componentes/graficos/barras";
import type { Kpi } from "../componentes/graficos/kpi";
import { formatarDecimal, formatarNumero } from "../formato";
import { formatarDataBrasilia } from "../textos";
import type { Cargo, Filtros } from "../store";
import { cargoDaApi } from "./adaptadores";
import type { ParCorrelacao, PerfilRede, RecorteCorrelacao, RedeCandidato, RespostaCorrelacoes, RespostaRedes, RespostaSerieRedes } from "./contrato";

type Excluidos = RespostaRedes["excluidos"];

const semAcento = (s: string): string => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const f1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const f2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CARGO_CURTO: Readonly<Record<Cargo, string>> = {
  deputado_federal: "Dep. federal", deputado_estadual: "Dep. estadual", senador: "Senador", governador: "Governador", presidente: "Presidente",
};

/** Cargos com possibilidade de 2º turno: só neles o aviso do 2º turno faz sentido. */
export const CARGOS_COM_SEGUNDO_TURNO: readonly Cargo[] = ["presidente", "governador"];

/** Filtros → query de `/api/redes*`. Redes só existem em 2026: não há `ano`. */
export function paramsRedes(f: Readonly<Filtros>): Record<string, string> {
  const q: Record<string, string> = { grupo: f.grupo, cargo: cargoDaApi(f.cargo) };
  if (f.uf !== "BR") q["uf"] = f.uf;
  return q;
}

const plural = (n: number, um: string, varios: string): string => `${formatarNumero(n)} ${n === 1 ? um : varios}`;

/** O que está sendo comparado, em uma frase: rede, quantas candidaturas, de quem, cargo, UF, e quantas têm número. */
export function fraseResumo(r: RespostaRedes, rotuloGrupo: string, f: Readonly<Filtros>): string {
  const a = r.agregado;
  const uf = f.uf === "BR" ? "Brasil" : f.uf;
  const indisp = Math.max(a.n_candidatos - a.n_com_dados, 0);
  return `Instagram de ${plural(a.n_candidatos, "candidatura", "candidaturas")} do ${rotuloGrupo} · ${CARGO_CURTO[f.cargo]} · ${uf} — ${formatarNumero(a.n_com_dados)} com perfil público, ${formatarNumero(indisp)} indisponíveis.`;
}

/** Por que cada candidatura ficou de fora dos números; só os motivos que existem. */
export function detalheExcluidos(e: Excluidos): string {
  return ([
    ["Sem Instagram declarado", e.sem_instagram], ["Declararam, ainda sem coleta", e.nao_coletado],
    ["Conta pessoal ou inexistente", e.indisponivel], ["Sem votos registrados", e.sem_votos],
  ] as const).filter(([, n]) => n > 0).map(([t, n]) => `${t}: ${formatarNumero(n)}`).join(" · ");
}

/** Chave de procedência dos KPIs: a tela liga ao rótulo "Instagram — API oficial da Meta, coletado em …". */
export const FONTE_INSTAGRAM = "instagram";

/** Cartões do topo. O que a API não calculou (nulo) fica de fora — nunca vira zero. */
export function kpisDeRedes(r: RespostaRedes): Kpi[] {
  const a = r.agregado;
  const base = { fonte: FONTE_INSTAGRAM } as const;
  const k: Kpi[] = [{ ...base, rotulo: "Contas com números", ajuda: "seguidores_votos", valor: a.n_com_dados, formato: "inteiro", unidade: `de ${plural(a.n_candidatos, "candidatura", "candidaturas")}` }];
  if (a.seguidores_total !== null) k.push({ ...base, rotulo: "Seguidores somados", ajuda: "seguidores_votos", valor: a.seguidores_total, formato: "inteiro", unidade: "seguidores nas contas com números" });
  if (a.mediana_seguidores !== null) k.push({ ...base, rotulo: "Mediana de seguidores", ajuda: "seguidores_votos", valor: a.mediana_seguidores, formato: "inteiro", unidade: "seguidores por conta" });
  if (a.mediana_posts_semana_campanha !== null) k.push({ ...base, rotulo: "Posts por semana na campanha (mediana)", ajuda: "ritmo_posts", valor: a.mediana_posts_semana_campanha, formato: "decimal", unidade: "posts por semana" });
  if (a.mediana_pct_video !== null) k.push({ ...base, rotulo: "Vídeos e reels (mediana)", ajuda: "ritmo_posts", valor: a.mediana_pct_video, formato: "pontos", unidade: "% dos posts" });
  if (a.mediana_engajamento_mediano !== null) k.push({ ...base, rotulo: "Engajamento por post (mediana)", ajuda: "engajamento", valor: a.mediana_engajamento_mediano, formato: "pontos", unidade: "% dos seguidores por post" });
  return k;
}

// ---- Correlação em linguagem simples ----

export interface Leitura { resumo: string; detalhe: string }

function forca(rho: number): string {
  const a = Math.abs(rho);
  return a < 0.1 ? "nenhuma" : a < 0.3 ? "fraca" : a < 0.5 ? "moderada" : a < 0.7 ? "forte" : "muito forte";
}

/** ρ de Spearman → frase curta + linha técnica (IC, n) + a ressalva de causa. Abaixo do n mínimo não há número. */
export function interpretarCorrelacao(p: ParCorrelacao): Leitura {
  if (p.rho === null) return { resumo: `Poucos candidatos com dados (${formatarNumero(p.n)}); só calculamos com pelo menos ${formatarNumero(p.n_minimo)}.`, detalhe: "" };
  const nivel = forca(p.rho);
  const resumo = nivel === "nenhuma"
    ? "Quase nenhuma relação: ter mais ou menos não indica mais ou menos votos."
    : p.rho > 0 ? `Relação ${nivel}: quem tem mais, tende a ter mais votos.` : `Relação ${nivel} inversa: quem tem mais, tende a ter menos votos.`;
  const ic = p.ic_inf !== null && p.ic_sup !== null ? ` (intervalo de ${formatarNumero(Math.round(p.nivel_ic * 100))} %: ${f2.format(p.ic_inf)} a ${f2.format(p.ic_sup)})` : "";
  return { resumo, detalhe: `Coeficiente de Spearman ${f2.format(p.rho)}${ic}, com ${formatarNumero(p.n)} candidatos. Mostra associação, não prova causa.` };
}

export function recorteDaTela(c: RespostaCorrelacoes, cargoApi: string): RecorteCorrelacao | null {
  return c.recortes.find((r) => r.cargo === cargoApi) ?? null;
}

// ---- Dispersão seguidores × votos ----

/** Fora de 1/1,5× a 1,5× do esperado já é diferença que se vê; dentro disso é ruído de uma reta descritiva. */
export const LIMIAR_ESPERADO = 1.5;
export type ClasseEsperado = "acima" | "abaixo" | "neutro";

export function classeDoEsperado(razao: number | null): ClasseEsperado {
  if (razao === null) return "neutro";
  return razao >= LIMIAR_ESPERADO ? "acima" : razao <= 1 / LIMIAR_ESPERADO ? "abaixo" : "neutro";
}

/** "2,0× o esperado (acima)": 2 = o dobro do voto que a reta prevê para o tamanho da conta. */
export function textoVotoEsperado(razao: number | null): string {
  if (razao === null) return "indisponível";
  const c = classeDoEsperado(razao);
  return `${f1.format(razao)}× o esperado (${c === "neutro" ? "dentro do esperado" : c})`;
}

export interface PontoSeguidores {
  id: string;
  rotulo: string;
  seguidores: number;
  votos: number;
  razao: number | null;
  classe: ClasseEsperado;
  foto: string | null;
  linkPerfil: string;
  detalhe: readonly (readonly [string, string])[];
}

export function pontosSeguidoresVotos(r: RecorteCorrelacao): PontoSeguidores[] {
  return r.pontos.map((p) => ({
    id: String(p.sq_candidato), rotulo: p.nm_urna, seguidores: p.seguidores, votos: p.votos, razao: p.razao_obs_esperado,
    classe: classeDoEsperado(p.razao_obs_esperado), foto: p.foto_url, linkPerfil: p.link,
    detalhe: [
      ["UF", p.sg_uf], ["Instagram", `@${p.username}`], ["Seguidores", formatarNumero(p.seguidores)], ["Votos", formatarNumero(p.votos)],
      ["Voto observado ÷ esperado", textoVotoEsperado(p.razao_obs_esperado)],
    ],
  }));
}

// ---- Ranking e busca ----

export interface RankingsRedes { seguidores: Barra[]; engajamento: Barra[]; acimaDoEsperado: Barra[] }

const topo = (itens: readonly Barra[], limite: number): Barra[] => [...itens].sort((a, b) => b.valor - a.valor).slice(0, limite);

/** Top N por seguidores, engajamento e voto acima do esperado — só quem tem número. */
export function rankingsDeRedes(r: RespostaRedes, limite = 10): RankingsRedes {
  const det = (c: RedeCandidato): [string, string][] => [["UF", c.sg_uf], ["Votos", c.votos === null ? "indisponível" : formatarNumero(c.votos)]];
  const com = r.candidatos.filter((c) => c.tem_dados);
  const barras = (valor: (c: RedeCandidato) => number | null): Barra[] =>
    com.flatMap((c) => { const v = valor(c); return v === null ? [] : [{ rotulo: c.nm_urna, valor: v, detalhe: det(c) }]; });
  return {
    seguidores: topo(barras((c) => c.seguidores), limite),
    engajamento: topo(barras((c) => c.engajamento_mediano), limite),
    acimaDoEsperado: topo(barras((c) => c.voto_esperado?.razao_obs_esperado ?? null), limite),
  };
}

/** Busca por trecho do nome de urna (sem acento/caixa). Menos de 2 letras não lista ninguém. */
export function buscarCandidatos(candidatos: readonly RedeCandidato[], consulta: string, limite = 8): RedeCandidato[] {
  const q = semAcento(consulta.trim());
  if (q.length < 2) return [];
  return candidatos.filter((c) => semAcento(c.nm_urna).includes(q)).slice(0, limite);
}

export function descreverStatus(c: RedeCandidato): string {
  switch (c.status) {
    case "ok": return "Perfil público com números";
    case "nao_comercial": return "Conta pessoal: o Instagram só informa números de contas comerciais ou de criador";
    case "nao_encontrado": return "Perfil não encontrado no Instagram";
    case "nao_coletado": return "Declarou o perfil; ainda sem coleta";
    case "sem_rede": return "Não declarou Instagram ao TSE";
  }
}

/** Conta analisada do candidato (a de mais seguidores entre as com número), se houver. */
export const perfilAnalisado = (c: RedeCandidato): PerfilRede | undefined => c.perfis.find((p) => p.analisado) ?? c.perfis[0];

// ---- Ritmo de posts ----

export interface PontoRitmo { janela: "pre_campanha" | "campanha" | "pos_eleicao"; rotulo: string; grupo: number | null; candidato: number | null }

const JANELAS: readonly (readonly [PontoRitmo["janela"], string])[] = [
  ["pre_campanha", "Antes da campanha"], ["campanha", "Durante a campanha"], ["pos_eleicao", "Depois da eleição"],
];

function mediana(v: readonly number[]): number | null {
  if (v.length === 0) return null;
  const o = [...v].sort((a, b) => a - b);
  const m = Math.floor(o.length / 2);
  return o.length % 2 ? (o[m] ?? null) : (((o[m - 1] ?? 0) + (o[m] ?? 0)) / 2);
}

/**
 * Posts por semana em cada janela: mediana do grupo (só contas com número) e o candidato em foco.
 * Janela com menos de 7 dias vem `null` da API (taxa semanal sem sentido) e continua `null` aqui.
 */
export function ritmoPorJanela(r: RespostaRedes, sqFoco: number | null): PontoRitmo[] {
  const taxa = (c: RedeCandidato, j: PontoRitmo["janela"]): number | null => c.janelas.find((x) => x.janela === j)?.posts_por_semana ?? null;
  const com = r.candidatos.filter((c) => c.tem_dados);
  const foco = sqFoco === null ? undefined : r.candidatos.find((c) => c.sq_candidato === sqFoco && c.tem_dados);
  return JANELAS.map(([janela, rotulo]) => ({
    janela, rotulo,
    grupo: mediana(com.flatMap((c) => { const t = taxa(c, janela); return t === null ? [] : [t]; })),
    candidato: foco ? taxa(foco, janela) : null,
  }));
}

// ---- Série de seguidores ----

export type SituacaoSerie =
  | { tipo: "um_ponto"; username: string; link: string; seguidores: number; nota: string }
  | { tipo: "linha"; username: string; link: string; pontos: RespostaSerieRedes["series"][number]["pontos"]; resumo: string };

const sinal = (n: number, texto: string): string => `${n > 0 ? "+" : n < 0 ? "−" : ""}${texto}`;

/** Com um ponto só há um número, não uma linha; com dois ou mais, a variação entre o primeiro e o último. */
export function situacaoDaSerie(s: RespostaSerieRedes, indice = 0): SituacaoSerie {
  const conta = s.series[indice];
  if (!conta) throw new Error("série sem nenhuma conta");
  const { username, link, pontos, resumo } = conta;
  if (pontos.length < 2 || resumo.delta_abs === null) {
    return {
      tipo: "um_ponto", username, link, seguidores: resumo.seguidores_final,
      nota: `Primeira coleta em ${formatarDataBrasilia(s.primeira_coleta)}. A série cresce a cada dia.`,
    };
  }
  const dias = resumo.dias === null ? "" : ` em ${resumo.dias === 1 ? "1 dia" : `${formatarDecimal(resumo.dias)} dias`}`;
  const pct = resumo.delta_pct === null ? "" : ` (${sinal(resumo.delta_pct, `${formatarDecimal(Math.abs(resumo.delta_pct))} %`)})`;
  return { tipo: "linha", username, link, pontos, resumo: `${sinal(resumo.delta_abs, formatarNumero(Math.abs(resumo.delta_abs)))} seguidores${pct}${dias}` };
}
