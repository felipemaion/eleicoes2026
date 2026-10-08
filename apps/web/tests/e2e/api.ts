import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";

const lerFixture = (nome: string): string => readFileSync(new URL(`../fixtures/api/${nome}.json`, import.meta.url), "utf-8");

/** Fixtures do contrato (tipadas pelo OpenAPI em contrato-fixtures.test.ts) respondem em /api/**. */
export async function simularApi(page: Page, sobrescrever: Record<string, { status: number; corpo?: string }> = {}): Promise<string[]> {
  const urls: string[] = [];
  const rotas: Record<string, string> = {
    "/api/meta": "meta", "/api/grupos": "grupos", "/api/candidatos": "candidatos", "/api/candidatos/ufs": "ufs", "/api/busca": "busca", "/api/mapa": "mapa", "/api/mapa/pontos": "mapa-pontos",
    "/api/gastos": "gastos", "/api/comparativo": "comparativo", "/api/candidatos/2026/1": "ficha", "/api/evolucao/pessoas": "pessoas", "/api/municipios/2800308": "municipio",
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
    await route.fulfill({ contentType: "application/json", body: corpo });
  });
  return urls;
}

