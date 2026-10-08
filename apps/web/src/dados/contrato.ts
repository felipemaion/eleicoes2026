/**
 * TIPOS PROVISÓRIOS do contrato da API (T-B02), escritos a partir do brief enquanto
 * `docs/api/openapi.json` só tem /health e /meta. Único módulo a trocar quando o OpenAPI
 * ganhar os endpoints: rode `pnpm gen:api` e reexporte de `./gerado/api` aqui, sem mexer
 * em adaptadores nem telas. Não espalhe tipos de resposta fora deste arquivo.
 */
export interface Meta {
  /** Data de geração dos arquivos do TSE (DT_GERACAO), ISO 8601. */
  dt_geracao: string | null;
  fonte: string;
}

export interface Grupo {
  id: string;
  rotulo: string;
  ano: number;
  n_candidaturas: number;
}

export interface ComparacaoDef {
  id: string;
  rotulo: string;
  antes: string;
  depois: string;
}

export interface RespostaGrupos {
  grupos: Grupo[];
  comparacoes: ComparacaoDef[];
}

export interface Candidato {
  sq_candidato: string;
  ano: number;
  nome: string;
  partido: string;
  cargo: string;
  uf: string;
  grupo: string;
  votos: number;
  pct_validos: number;
  penetracao: number;
  resultado: string;
  /** Indicado pelo grupo (recorte "só indicados"). */
  indicado: boolean;
}

export interface VotoMunicipio {
  cd_mun_ibge: string;
  nome: string;
  votos: number;
  taxa: number;
}

export interface FonteReceita {
  fonte: string;
  valor: number;
}

export interface Ficha {
  candidato: Candidato;
  votos_municipios: VotoMunicipio[];
  gastos: { contratado: number; pago: number; custo_voto_contratado: number | null; custo_voto_pago: number | null };
  receitas: FonteReceita[];
  contas_parciais: boolean;
}

export type EscalaSugerida = "quantil" | "divergente" | "log";

export interface DetalheMapa {
  nome?: string;
  votos: number;
  aptos: number;
  taxa: number;
}

export interface RespostaMapa {
  valores: Record<string, number>;
  detalhes: Record<string, DetalheMapa>;
  escala_sugerida: EscalaSugerida;
  /** Só para escala_sugerida = "divergente": semiamplitude simétrica em torno de 0. */
  extensao?: number;
  tipo: "taxa" | "razao" | "diferenca";
  unidade: string;
  denominador: string;
}

export interface PontoVoto {
  lat: number;
  lon: number;
  votos: number;
}

export interface GastoCandidato {
  id: string;
  rotulo: string;
  votos: number;
  custo_contratado: number;
  custo_pago: number;
}

export interface RespostaGastos {
  candidatos: GastoCandidato[];
  receita_por_fonte: { rotulo: string; valores: Record<string, number> }[];
  custo_voto_contratado: number | null;
  custo_voto_pago: number | null;
  pct_publico: number;
  pct_autofinanciamento: number;
  contas_parciais: boolean;
  /** Mês-base do IPCA usado nos valores de 2022 (ex.: "2026-09"). */
  mes_base_deflator: string;
}

export interface MunicipioComparado {
  cd_mun_ibge: string;
  nome: string;
  /** Δ penetração por AMC (2026 − 2022), em fração dos aptos. */
  delta_penetracao: number;
  retencao: number | null;
}

export interface RespostaComparativo {
  rotulo_antes: string;
  rotulo_depois: string;
  kpis: { penetracao_antes: number; penetracao_depois: number; retencao: number | null };
  municipios: MunicipioComparado[];
  candidatos: { rotulo: string; antes: number; depois: number }[];
  /** Penetração por município nos dois anos (mesmas quebras no mapa). */
  penetracao_antes: Record<string, number>;
  penetracao_depois: Record<string, number>;
  mes_base_deflator: string;
}

export interface RespostaMunicipio {
  cd_mun_ibge: string;
  nome: string;
  uf: string;
  aptos: number;
  grupos: { grupo: string; rotulo: string; votos: number; taxa: number }[];
}

export interface KpisGrupo {
  votos: number;
  votos_nominais: number;
  votos_legenda: number;
  pct_validos: number;
  penetracao: number;
  /** Penetração do grupo de comparação (MBL 2022) no mesmo cargo. */
  penetracao_comparada: number | null;
  eleitos: number;
  candidaturas_aptas: number;
  custo_voto_contratado: number | null;
  pct_publico: number;
  delta_penetracao: number | null;
}

export interface RespostaCandidatos {
  candidatos: Candidato[];
  kpis: KpisGrupo | null;
  contas_parciais: boolean;
  dt_geracao: string | null;
}
