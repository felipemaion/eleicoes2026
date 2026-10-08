import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

test("visão geral: KPIs, ranking, avisos públicos e ajuda '?' por teclado", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  await expect(page.locator(".kpi")).toHaveCount(5);
  await expect(page.locator("aside.avisos").getByText("Contas de 2026 parciais.")).toBeVisible();
  await expect(page.locator("rect.marca")).toHaveCount(3);
  await expect(page.getByRole("contentinfo")).toContainText("2026-10-07");
  const ajuda = page.getByRole("button", { name: /Ajuda: Custo por voto/ });
  await ajuda.focus();
  await page.keyboard.press("Enter");
  await expect(ajuda).toHaveAttribute("aria-expanded", "true");
  await expect(ajuda.locator("xpath=following-sibling::*").getByText("Denominador")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(ajuda).toHaveAttribute("aria-expanded", "false");
});

test("mapa: coroplético, troca de indicador sem recarregar geometria e painel do município", async ({ page }) => {
  const urls = await simularApi(page);
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator(".mapa-quadro canvas")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-legenda svg")).toContainText("Denominador");
  await page.getByLabel("Indicador").selectOption("pct_validos");
  await expect.poll(() => urls.some((u) => u.includes("indicador=pct_validos"))).toBe(true);
  await expect(page.locator(".mapa-quadro canvas")).toHaveCount(1);
  // sem PMTiles publicados, só há o nível município
  await expect(page.getByLabel("Nível").locator("option[value=zona]")).toHaveAttribute("disabled", "");
  await expect(page.getByText(/Geometria de demonstração/)).toHaveCount(0); // UF = SE
});

test("gastos: avisos, dispersão e receita por fonte, com tabela alternativa", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/gastos");
  await expect(page.locator("svg.grafico")).toHaveCount(2);
  await expect(page.getByText(/reais de set\/2026/)).toBeVisible();
  await expect(page.locator("aside.avisos").getByText("Contas de 2026 parciais.")).toBeVisible();
  await page.getByLabel("Base do custo").selectOption("pago");
  await page.locator("summary", { hasText: "Ver dados em tabela" }).first().click();
  await expect(page.locator("details[open] table")).toBeVisible();
});

test("evolução: três mapas, KPIs em ‰ e avisos de rezoneamento", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/evolucao");
  await expect(page.locator(".mapas-3 canvas")).toHaveCount(3, { timeout: 20_000 });
  await expect(page.getByText(/mesmas quebras de cor/)).toBeVisible();
  await expect(page.getByText("Zonas eleitorais mudaram.")).toBeVisible();
  await expect(page.locator("dl.kpis")).toContainText("6,1 ‰");
});

test("Como ler este painel: página pública renderizada do README", async ({ page }) => {
  await page.goto("/#/como-ler");
  await expect(page.getByRole("heading", { level: 2, name: "Como ler este painel" })).toBeVisible();
  await expect(page.locator("article.como-ler table").first()).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Telas" }).getByRole("link", { name: "Como ler este painel" })).toHaveAttribute("aria-current", "page");
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
  for (const rota of ["visao-geral", "gastos", "como-ler", "candidato?cand=2026:1"]) {
    await page.goto(`/#/${rota}`);
    await expect(page.locator("main h1")).toBeVisible();
    await page.waitForTimeout(400);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), `rota ${rota}`).toBeLessThanOrEqual(0);
  }
});
