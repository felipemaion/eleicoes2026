import type { Tela as Chave } from "../store";
import { tela as candidato } from "./candidato";
import { tela as comoLer } from "./como-ler";
import { tela as evolucao } from "./evolucao";
import { tela as gastos } from "./gastos";
import { tela as mapa } from "./mapa";
import { tela as redes } from "./redes";
import type { Tela } from "./tipos";
import { tela as visaoGeral } from "./visao-geral";

export const TELAS_POR_CHAVE: Readonly<Record<Chave, Tela>> = {
  "visao-geral": visaoGeral,
  mapa,
  gastos,
  redes,
  evolucao,
  candidato,
  "como-ler": comoLer,
};
