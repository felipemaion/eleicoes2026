/**
 * Fluxos contra a API REAL local (`make dev` com dados processados). Fora do CI: só roda com
 * E2E_API_REAL=1 (o `vite preview` repassa /api para localhost:8000). Valida que o contrato
 * gerado do OpenAPI bate com o que o backend entrega de fato.
 */
import { expect, test } from "@playwright/test";

test.skip(process.env["E2E_API_REAL"] !== "1", "defina E2E_API_REAL=1 com a API em :8000");

test("API real: telas principais carregam sem alerta de erro", async ({ page }) => {
  for (const rota of ["visao-geral?uf=SE&cargo=deputado_federal", "gastos", "evolucao?uf=SE&cargo=deputado_federal"]) {
    await page.goto(`/#/${rota}`);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
});

test("API real: mapa de Sergipe colore e o painel do município responde", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE&cargo=deputado_federal");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 30_000 });
  await page.locator(".mapa-quadro").focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  await expect(page.locator(".painel-municipio h2")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
