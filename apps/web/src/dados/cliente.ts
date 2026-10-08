/**
 * Cliente da API. Stub tipado: os tipos de resposta virão de `docs/api/openapi.json`
 * via openapi-typescript quando o contrato existir — não escrever tipos de resposta à mão.
 */
export interface Meta {
  /** Data de geração dos arquivos do TSE (DT_GERACAO), ISO 8601. */
  dt_geracao: string | null;
  fonte: string;
}

export interface ClienteApi {
  meta(): Promise<Meta>;
}

export function criarCliente(base = "/api"): ClienteApi {
  return {
    async meta() {
      const r = await fetch(`${base}/meta`);
      if (!r.ok) throw new Error(`GET ${base}/meta falhou: ${String(r.status)}`);
      return (await r.json()) as Meta;
    },
  };
}
