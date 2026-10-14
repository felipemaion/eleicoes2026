import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";

const lerFixture = (nome: string): string => readFileSync(new URL(`../fixtures/api/${nome}.json`, import.meta.url), "utf-8");

const ROTULO_CARGO: Record<string, string> = { "DEPUTADO FEDERAL": "Dep. federal", "DEPUTADO ESTADUAL": "Dep. estadual" };

/** Espelha cargo, UF e destaque pedidos na fixture de deputados (a API real recorta por eles); presidente usa a própria fixture. */
function referenciasDaConsulta(url: URL, deputado: string): string {
  const cargo = url.searchParams.get("cargo") ?? "";
  if (cargo === "PRESIDENTE") return lerFixture("referencias-presidente");
  const uf = url.searchParams.get("uf") ?? "SP";
  const sq = url.searchParams.get("sq");
  const d = JSON.parse(deputado) as { cargo: string; uf: string; rotulo: string; destaque: number | null; nossos: { rotulo: string; candidatos: { sq_candidato: number; destacado: boolean }[] }; referencia: { rotulo: string } };
  const c = ROTULO_CARGO[cargo] ?? "Dep. federal";
  d.cargo = cargo; d.uf = uf;
  d.nossos.rotulo = `Missão · ${c} · ${uf}`;
  d.referencia.rotulo = `5 eleitos mais votados de outros partidos em ${uf}`;
  d.rotulo = `${d.nossos.rotulo} × ${d.referencia.rotulo}`;
  if (sq !== null) { d.destaque = Number(sq); d.nossos.candidatos.forEach((x) => { x.destacado = String(x.sq_candidato) === sq; }); }
  return JSON.stringify(d);
}

/** Fixtures do contrato (tipadas pelo OpenAPI em contrato-fixtures.test.ts) respondem em /api/**. */
export async function simularApi(page: Page, sobrescrever: Record<string, { status: number; corpo?: string }> = {}): Promise<string[]> {
  const urls: string[] = [];
  const rotas: Record<string, string> = {
    "/api/meta": "meta", "/api/grupos": "grupos", "/api/candidatos": "candidatos", "/api/candidatos/ufs": "ufs", "/api/busca": "busca", "/api/mapa": "mapa", "/api/mapa/pontos": "mapa-pontos",
    "/api/gastos": "gastos", "/api/comparativo": "comparativo", "/api/candidatos/2026/1": "ficha", "/api/evolucao/pessoas": "pessoas", "/api/municipios/2800308": "municipio",
    "/api/referencias": "referencias-deputado", "/api/redes": "redes", "/api/redes/correlacoes": "redes-correlacoes", "/api/redes/serie": "redes-serie",
  };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    urls.push(url.pathname + url.search);
    const forca = sobrescrever[url.pathname];
    if (forca) { await route.fulfill({ status: forca.status, contentType: "application/json", body: forca.corpo ?? "{}" }); return; }
    // Qualquer município responde com a mesma fixture (o teste escolhe o primeiro da ordem alfabética).
    const nome = url.pathname.startsWith("/api/municipios/") ? "municipio" : rotas[url.pathname];
    if (!nome) { await route.fulfill({ status: 404, body: "{}" }); return; }
    let corpo = lerFixture(nome);
    // O mock devolve a mesma fixture de /mapa; o indicador pedido é espelhado para a legenda mudar de verdade.
    if (url.pathname === "/api/mapa" && url.searchParams.get("indicador") === "pct_validos") {
      corpo = JSON.stringify({ ...(JSON.parse(corpo) as object), indicador: "pct_validos", unidade: "%" });
    }
    if (url.pathname === "/api/referencias") corpo = referenciasDaConsulta(url, corpo);
    await route.fulfill({ contentType: "application/json", body: corpo });
  });
  return urls;
}

