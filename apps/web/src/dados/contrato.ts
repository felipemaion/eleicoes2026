/**
 * Tipos do contrato da API: SEMPRE derivados de `./gerado/api` (`pnpm gen:api` a partir de
 * `docs/api/openapi.json`). Nada aqui é escrito à mão — só apelidos legíveis. O backend é a
 * fonte de verdade; divergência de semântica vai para o handoff, não para um tipo paralelo.
 */
import type { components, paths } from "./gerado/api";

type S = components["schemas"];

export type Meta = S["Meta"];
export type RespostaGrupos = S["GruposResposta"];
export type Grupo = S["GrupoResumo"];
export type ComparacaoDef = S["ComparacaoResumo"];
export type Candidato = S["CandidatoResumo"];
export type Abrangencia = S["Abrangencia"];
export type CandidaturaBusca = S["CandidaturaBusca"];
export type RespostaBusca = S["ResultadoBusca"];
export type RespostaCandidatos = S["ListaCandidatos"];
export type Ficha = S["FichaCandidato"];
export type VotoMunicipio = S["VotosMunicipio"];
export type RespostaMapa = S["Mapa"];
export type DetalheMapa = S["Detalhe"];
export type EscalaSugerida = S["EscalaSugerida"];
export type PontoVoto = S["Ponto"];
export type RespostaPontos = S["Pontos"];
export type RespostaGastos = S["Gastos"];
export type GastoCandidato = S["GastoCandidato"];
export type RespostaComparativo = S["Comparativo"];
export type MunicipioComparado = S["EvolucaoMunicipio"];
export type RespostaMunicipio = S["ResumoMunicipio"];
export type PessoaEvolucao = S["PessoaEvolucao"];
export type RespostaPessoas = S["ListaPessoas"];
export type RespostaUfs = S["UfsDisponiveis"];
export type Fonte = S["Fonte"];
export type LinkOficial = S["Link"];
export type GastosFicha = S["GastosCandidato"];

/** Valores aceitos pela API (enums do OpenAPI). */
export type CargoApi = S["Cargo"];
export type UfApi = S["UF"];
export type IndicadorApi = S["Indicador"];
export type NivelApi = S["Nivel"];

/** Query de um endpoint, tirada do OpenAPI — o compilador acusa parâmetro renomeado. */
export type QueryDe<C extends keyof paths> = paths[C] extends { get: { parameters: { query?: infer Q } } } ? Q : never;
