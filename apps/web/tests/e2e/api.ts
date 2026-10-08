import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";

const lerFixture = (nome: string): string => readFileSync(new URL(`../fixtures/api/${nome}.json`, import.meta.url), "utf-8");

/** A API real ainda não existe: as fixtures do contrato respondem em /api/**. */
export async function simularApi(page: Page, sobrescrever: Record<string, { status: number; corpo?: string }> = {}): Promise<string[]> {
  const urls: string[] = [];
  const rotas: Record<string, string> = {
    "/api/meta": "meta", "/api/grupos": "grupos", "/api/candidatos": "candidatos", "/api/mapa": "mapa", "/api/mapa/pontos": "mapa-pontos",
    "/api/gastos": "gastos", "/api/comparativo": "comparativo", "/api/candidatos/2026/1": "ficha", "/api/municipios/2800308": "municipio",
  };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    urls.push(url.pathname + url.search);
    const forca = sobrescrever[url.pathname];
    if (forca) { await route.fulfill({ status: forca.status, contentType: "application/json", body: forca.corpo ?? "{}" }); return; }
    const nome = url.pathname === "/api/mapa" && url.searchParams.get("indicador") === "swing" ? "mapa-swing" : rotas[url.pathname];
    if (!nome) { await route.fulfill({ status: 404, body: "{}" }); return; }
    await route.fulfill({ contentType: "application/json", body: lerFixture(nome) });
  });
  return urls;
}

