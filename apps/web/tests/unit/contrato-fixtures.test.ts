/**
 * As fixtures são do contrato: cada JSON é atribuído ao tipo gerado do OpenAPI. Se o backend
 * renomear um campo, `pnpm typecheck` quebra aqui antes de qualquer tela quebrar em produção.
 */
import { describe, expect, it } from "vitest";
import candidatos from "../fixtures/api/candidatos.json";
import comparativo from "../fixtures/api/comparativo.json";
import ficha from "../fixtures/api/ficha.json";
import gastos from "../fixtures/api/gastos.json";
import grupos from "../fixtures/api/grupos.json";
import mapa from "../fixtures/api/mapa.json";
import pontos from "../fixtures/api/mapa-pontos.json";
import meta from "../fixtures/api/meta.json";
import municipio from "../fixtures/api/municipio.json";
import type { Meta, Ficha, RespostaCandidatos, RespostaComparativo, RespostaGastos, RespostaGrupos, RespostaMapa, RespostaMunicipio, RespostaPontos } from "../../src/dados/contrato";

describe("fixtures seguem o OpenAPI gerado", () => {
  it("tipam contra components['schemas']", () => {
    const todas: unknown[] = [
      meta satisfies Meta,
      grupos satisfies RespostaGrupos,
      candidatos satisfies RespostaCandidatos,
      ficha satisfies Ficha,
      mapa satisfies RespostaMapa,
      pontos satisfies RespostaPontos,
      gastos satisfies RespostaGastos,
      comparativo satisfies RespostaComparativo,
      municipio satisfies RespostaMunicipio,
    ];
    expect(todas).toHaveLength(9);
  });
});
