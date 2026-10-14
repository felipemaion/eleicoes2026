import { expect, test } from "@playwright/test";
import { simularApi } from "./api";
import { pastaCapturas } from "./capturas";

const CAPTURAS = pastaCapturas();

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("comparar: três blocos bem separados; cada um diz o que está sendo comparado", async ({ page }) => {
  await page.goto("/#/comparar?cargo=deputado_estadual");
  await expect(page.getByRole("heading", { level: 1, name: "Comparar com outros partidos" })).toBeVisible();
  const grupo = page.getByRole("group", { name: "O que comparar" });
  await expect(grupo.getByRole("button")).toHaveText(["Presidente", "Dep. federal", "Dep. estadual"]);
  await expect(grupo.getByRole("button", { name: "Dep. estadual" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".comparar-cabecalho h2")).toHaveText("Missão · Dep. estadual · SP × 5 eleitos mais votados de outros partidos em SP");
  await expect(page.locator(".lado-nosso")).toBeVisible();
  await expect(page.locator(".lado-ref")).toBeVisible();
  await expect(page.locator(".tabela-comparar thead th.col-ref")).toHaveCount(5);
  await page.screenshot({ path: `${CAPTURAS}/T-W26-comparar-desktop.png`, fullPage: true });

  await grupo.getByRole("button", { name: "Dep. federal" }).click();
  await expect(page.locator(".comparar-cabecalho h2")).toHaveText(/Missão · Dep\. federal · SP × 5 eleitos/);

  await grupo.getByRole("button", { name: "Presidente" }).click();
  await expect(page.locator(".comparar-cabecalho h2")).toHaveText("Renan Santos (Missão) × 5 presidenciáveis");
  await expect(page.locator("#uf-comparar, select[name=uf-comparar]")).toHaveCount(0);
  await expect(page.locator(".tabela-comparar thead th.col-ref")).toHaveCount(5);
  await expect(page.locator(".tabela-comparar thead th", { hasText: "FLÁVIO BOLSONARO" })).toBeVisible();
  await expect(page.locator(".avisos")).toContainText("Presidente: escolha editorial");
  await page.screenshot({ path: `${CAPTURAS}/T-W26-comparar-presidente.png`, fullPage: true });
});

test("comparar: troca de UF refaz a comparação na nova UF", async ({ page }) => {
  await page.goto("/#/comparar?cargo=deputado_federal&uf=SP");
  await expect(page.locator(".comparar-cabecalho h2")).toContainText("· SP ×");
  await page.locator("select[name=uf-comparar]").selectOption("SE");
  await expect(page.locator(".comparar-cabecalho h2")).toHaveText("Missão · Dep. federal · SE × 5 eleitos mais votados de outros partidos em SE");
});

test("comparar: o nosso candidato padrão é o mais votado e a busca troca por outro", async ({ page }) => {
  await page.goto("/#/comparar?cargo=deputado_estadual&uf=SP");
  await expect(page.locator(".tabela-comparar thead th.col-nosso")).toContainText("ANA SOUZA 0");
  await page.getByLabel("Escolher o candidato do Missão").fill("hugo");
  await page.getByRole("button", { name: /HUGO ALVES/ }).click();
  await expect(page.locator(".tabela-comparar thead th.col-nosso")).toContainText("HUGO ALVES");
  await expect(page.locator(".grafico-indice rect.marca").first()).toBeVisible();
  await expect(page.locator(".grafico-indice")).toContainText("×");
});

test("comparar: dado ausente aparece como 'sem dado' (nunca zero), com motivo; selo de declaração incompleta", async ({ page }) => {
  await page.goto("/#/comparar?cargo=deputado_estadual&uf=SP");
  const celulas = page.locator(".tabela-comparar td.sem-dado");
  expect(await celulas.count()).toBeGreaterThan(0);
  await expect(celulas.first()).toContainText("sem dado");
  await expect(page.locator(".tabela-comparar tbody")).not.toContainText("R$ 0,00");
  await page.getByLabel("Escolher o candidato do Missão").fill("carla");
  await page.getByRole("button", { name: /CARLA DIAS/ }).click();
  await expect(page.locator(".col-nosso .selo-alerta")).toHaveText("possível declaração incompleta");
  await expect(page.locator(".tabela-comparar tbody th", { hasText: "Receita por voto" })).toBeVisible();
  await expect(page.locator(".tabela-comparar tbody th", { hasText: "Despesa ÷ receita" })).toBeVisible();
});

test("comparar: tooltips ficam inteiros dentro da janela (cabeçalho e 'sem dado')", async ({ page }) => {
  await page.goto("/#/comparar?cargo=deputado_estadual&uf=SP");
  const vp = page.viewportSize() ?? { width: 1280, height: 720 };
  const alvos = [page.locator(".tabela-comparar thead th.col-ref a").last(), page.locator(".tabela-comparar thead th.col-nosso a"), page.locator(".tabela-comparar td.sem-dado span").first()];
  for (const alvo of alvos) {
    await alvo.scrollIntoViewIfNeeded();
    await alvo.hover();
    const balao = page.locator(".tooltip-flutuante:not([hidden])");
    await expect(balao).toBeVisible();
    const caixa = await balao.boundingBox();
    expect(caixa).not.toBeNull();
    expect(caixa?.x).toBeGreaterThanOrEqual(0);
    expect(caixa?.y).toBeGreaterThanOrEqual(0);
    expect((caixa?.x ?? 0) + (caixa?.width ?? 0)).toBeLessThanOrEqual(vp.width);
    expect((caixa?.y ?? 0) + (caixa?.height ?? 0)).toBeLessThanOrEqual(vp.height);
    await page.mouse.move(2, 2);
  }
});

test("comparar: no celular (390 px) empilha, sem rolagem horizontal", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const cargo of ["deputado_estadual", "presidente"]) {
    await page.goto(`/#/comparar?cargo=${cargo}&uf=SP`);
    await expect(page.locator(".tabela-comparar")).toBeVisible();
    const larg = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, vis: window.innerWidth }));
    expect(larg.doc).toBeLessThanOrEqual(larg.vis);
  }
  await page.goto("/#/comparar?cargo=deputado_estadual&uf=SP");
  await expect(page.locator(".grafico-indice rect.marca").first()).toBeVisible();
  await page.screenshot({ path: `${CAPTURAS}/T-W26-comparar-mobile.png`, fullPage: true });
});
