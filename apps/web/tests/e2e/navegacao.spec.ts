import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

test.beforeEach(async ({ page }) => { await simularApi(page); });

const TELAS = ["Visão geral", "Mapa", "Gastos", "Evolução 2022×2026", "Candidato"];

test("navega entre as 5 telas por mouse e teclado", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Telas" });
  for (const nome of TELAS) await expect(nav.getByRole("link", { name: nome })).toBeVisible();

  await nav.getByRole("link", { name: "Mapa" }).click();
  await expect(page).toHaveURL(/#\/mapa/);
  await expect(page.getByRole("heading", { level: 1, name: "Mapa" })).toBeVisible();

  await nav.getByRole("link", { name: "Gastos" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/gastos/);
  await expect(page.getByRole("heading", { level: 1, name: "Gastos" })).toBeVisible();
});

test("filtro de UF vai para a URL e rodapé mostra fonte", async ({ page }) => {
  await page.goto("/#/mapa");
  await page.getByLabel("UF").selectOption("SP");
  await expect(page).toHaveURL(/uf=SP/);
  await expect(page.getByRole("contentinfo")).toContainText("TSE");
  await expect(page.getByRole("contentinfo")).toContainText("dt_geracao");
});

test("sem rolagem horizontal em 360 px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  for (const rota of ["visao-geral", "mapa", "gastos", "evolucao", "candidato"]) {
    await page.goto(`/#/${rota}`);
    const sobra = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(sobra).toBeLessThanOrEqual(0);
  }
});

test("skip link foca o conteúdo sem resetar tela nem filtros", async ({ page }) => {
  await page.goto("/#/gastos?uf=SP&ano=2022");
  await page.getByRole("link", { name: "Pular para o conteúdo" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/gastos\?uf=SP&ano=2022/);
  await expect(page.locator("#principal")).toBeFocused();
  await expect(page.getByRole("heading", { level: 1, name: "Gastos" })).toBeVisible();
});
