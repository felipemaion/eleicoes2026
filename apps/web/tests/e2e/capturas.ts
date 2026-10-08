/**
 * Destino das capturas de tela dos e2e. Por padrão vão para `test-results/` (fora do git): rodar a suíte
 * não pode regenerar os PNGs versionados em `docs/registro/handoffs/img`. Só `SALVAR_CAPTURAS=1`
 * escreve em `docs/` — use ao produzir as capturas de um handoff.
 */
export const pastaCapturas = (subpasta = ""): string => {
  const raiz = process.env["SALVAR_CAPTURAS"] === "1" ? "../../docs/registro/handoffs/img" : "test-results/capturas";
  return subpasta === "" ? raiz : `${raiz}/${subpasta}`;
};
