import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

test("overlay de carregamento cobre a tela inteira quando a API demora e some depois", async ({ page }) => {
  await simularApi(page);
  await page.route("**/api/candidatos*", async (route) => {
    await new Promise((r) => setTimeout(r, 900));
    await route.fallback();
  });
  await page.goto("/#/visao-geral");
  const overlay = page.getByRole("status").filter({ hasText: "Carregando" });
  await expect(overlay).toBeVisible();
  const caixa = await overlay.boundingBox();
  const vp = page.viewportSize();
  expect(caixa?.width).toBe(vp?.width);
  expect(caixa?.height).toBe(vp?.height);
  await expect(overlay).toBeHidden({ timeout: 5000 });
  await expect(page.locator(".kpi").first()).toBeVisible();
});

test("respostas rápidas não fazem o overlay piscar", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  await expect(page.locator(".kpi").first()).toBeVisible();
  await expect(page.locator(".sobreposicao")).toBeHidden();
});

test("erro da API aparece com ação 'Tentar novamente'", async ({ page }) => {
  await simularApi(page, { "/api/candidatos": { status: 500 } });
  await page.goto("/#/visao-geral");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
});

test("tooltip do '?' fica legível, dentro da tela, e fecha com Esc (360 e 1280)", async ({ page }) => {
  await simularApi(page);
  for (const w of [360, 1280]) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto("/#/visao-geral");
    const ajuda = page.getByRole("button", { name: /Ajuda: Custo por voto/ });
    await ajuda.hover();
    const painel = ajuda.locator("xpath=following-sibling::*");
    await expect(painel).toBeVisible();
    const b = await painel.boundingBox();
    expect(b?.x).toBeGreaterThanOrEqual(0);
    expect((b?.x ?? 0) + (b?.width ?? 0)).toBeLessThanOrEqual(w);
    expect(b?.y).toBeGreaterThanOrEqual(0);
    // fundo sólido (não transparente)
    expect(await painel.evaluate((e) => getComputedStyle(e).backgroundColor)).not.toMatch(/rgba\(.*, 0\)/);
    await page.keyboard.press("Escape");
    await expect(painel).toBeHidden();
  }
});

test("ranking: barra tem tooltip com partido e UF no hover", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  await page.locator("rect.marca").first().hover();
  const tip = page.getByRole("tooltip").filter({ hasText: "Partido" });
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("UF");
});

test("sem rolagem horizontal em 360, 768, 1280 e 1920", async ({ page }) => {
  await simularApi(page);
  for (const w of [360, 768, 1280, 1920]) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto("/#/visao-geral");
    await expect(page.locator(".kpi").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
});

test("tema claro opcional lembrado e com a mesma estrutura", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  await page.getByRole("button", { name: "Tema claro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-tema", "claro");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-tema", "claro");
  await page.getByRole("button", { name: "Tema escuro" }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-tema", "claro");
});
