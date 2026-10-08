import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

test("visão geral: KPIs, ranking, comparação e recorte 'só indicados'", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  await expect(page.locator(".kpi")).toHaveCount(7);
  await expect(page.getByText("Contas de 2026 parciais")).toBeVisible();
  await expect(page.locator("rect.marca")).toHaveCount(3);
  await page.getByLabel("Só candidatos indicados pelo grupo").check();
  await expect(page.locator("rect.marca")).toHaveCount(2);
  await page.getByLabel("Comparar").selectOption("mbl2022_missao2026");
  await expect(page.getByLabel("Comparar")).toBeFocused();
  await expect(page.getByRole("contentinfo")).toContainText("2026-10-07");
});

test("mapa: coroplético, troca de indicador sem recarregar geometria e painel do município", async ({ page }) => {
  const urls = await simularApi(page);
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator(".mapa-quadro canvas")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-legenda svg")).toContainText("Denominador");
  await page.getByLabel("Indicador").selectOption("swing");
  await expect.poll(() => urls.some((u) => u.includes("indicador=swing"))).toBe(true);
  await expect(page.locator(".mapa-quadro canvas")).toHaveCount(1);
  await expect(page.getByLabel("Nível").locator("option[value=zona]")).toHaveAttribute("disabled", "");
  await page.getByLabel("Resumo do município").selectOption("2800308");
  await expect(page.locator(".painel-municipio")).toContainText("Aracaju");
});

test("gastos: avisos, dispersão e receita por fonte, com tabela alternativa", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/gastos");
  await expect(page.locator("svg.grafico")).toHaveCount(2);
  await expect(page.getByText("Valores de 2022 deflacionados pelo IPCA para setembro de 2026")).toBeVisible();
  await expect(page.getByText("Contas de 2026 parciais")).toBeVisible();
  await page.getByLabel("Base do custo").selectOption("pago");
  await page.locator("summary", { hasText: "Ver dados em tabela" }).first().click();
  await expect(page.locator("details[open] table")).toBeVisible();
});

test("evolução: três mapas e comparação por candidato", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/evolucao");
  await expect(page.locator(".mapas-3 canvas")).toHaveCount(3, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: /mesmos candidatos/ })).toBeVisible();
  await expect(page.getByText(/mesmas quebras de cor/)).toBeVisible();
  await expect(page.locator("svg.grafico")).toHaveCount(1);
});

test("candidato: escolher no seletor leva ao deep-link e mostra a ficha", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/candidato");
  await expect(page.getByText("Escolha um candidato para ver a ficha.")).toBeVisible();
  await page.getByLabel("Candidato").selectOption("2026:1");
  await expect(page).toHaveURL(/cand=2026%3A1/);
  await expect(page.getByRole("heading", { level: 2, name: "Ana Souza" })).toBeVisible();
  await expect(page.locator(".ficha svg.grafico")).toHaveCount(2);
  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "Ana Souza" })).toBeVisible();
});

test("erro da API mostra alerta e 'Tentar novamente' recupera", async ({ page }) => {
  await simularApi(page, { "/api/gastos": { status: 500 } });
  await page.goto("/#/gastos");
  await expect(page.getByRole("alert")).toContainText("500");
  await page.unroute("**/api/**");
  await simularApi(page);
  await page.getByRole("button", { name: "Tentar novamente" }).click();
  await expect(page.locator("svg.grafico")).toHaveCount(2);
});

test("sem rolagem horizontal em 360 px com dados", async ({ page }) => {
  await simularApi(page);
  await page.setViewportSize({ width: 360, height: 740 });
  for (const rota of ["visao-geral", "gastos", "candidato?cand=2026:1"]) {
    await page.goto(`/#/${rota}`);
    await expect(page.locator("main h1")).toBeVisible();
    await page.waitForTimeout(400);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  }
});
