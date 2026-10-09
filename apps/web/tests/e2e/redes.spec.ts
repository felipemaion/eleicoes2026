import { expect, test } from "@playwright/test";
import { simularApi } from "./api";
import { pastaCapturas } from "./capturas";

const CAPTURAS = pastaCapturas();
const SERIE_2 = '{"sq_candidato":1,"nm_urna":"Ana Souza","series":[{"username":"anasouza_14","link":"https://www.instagram.com/anasouza_14/","status":"ok","pontos":[{"coletado_em":"2026-10-08T12:00:00Z","seguidores":52000,"delta_abs":null,"delta_pct":null,"dias":null},{"coletado_em":"2026-10-09T12:00:00Z","seguidores":52340,"delta_abs":340,"delta_pct":0.65,"dias":1.0}],"resumo":{"n_snapshots":2,"seguidores_inicial":52000,"seguidores_final":52340,"delta_abs":340,"delta_pct":0.65,"dias":1.0}}],"primeira_coleta":"2026-10-08T12:00:00Z","coletado_em":"2026-10-09T12:00:00Z","avisos":[],"dt_geracao":"2026-10-06","fontes":[]}';

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("redes: frase-resumo, KPIs com fonte e dispersão com reta; clique abre o Instagram", async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __abertos: unknown[][] }).__abertos = [];
    window.open = ((...a: unknown[]) => { (window as unknown as { __abertos: unknown[][] }).__abertos.push(a); return null; });
  });
  await page.goto("/#/redes?uf=SE");
  await expect(page.getByRole("heading", { level: 1, name: "Redes sociais" })).toBeVisible();
  await expect(page.locator(".resumo-redes")).toContainText("Instagram de 14 candidaturas");
  await expect(page.locator(".resumo-redes")).toContainText("10 com perfil público, 4 indisponíveis");
  await page.locator("dl.kpis").first().getByRole("button", { name: /Fonte dos dados/ }).first().click();
  await expect(page.locator(".fonte-painel:not([hidden])")).toContainText("Instagram — API oficial da Meta, coletado em 08/10/2026");
  await page.keyboard.press("Escape");
  const pontos = page.locator(".grafico-redes-dispersao circle.marca");
  await expect(pontos).toHaveCount(10);
  await expect(page.locator(".grafico-redes-dispersao polyline.reta-ajuste")).toHaveCount(1);
  await pontos.first().scrollIntoViewIfNeeded();
  await page.locator('.grafico-redes-dispersao circle.marca[data-id="6"]').click();
  const abertos = await page.evaluate(() => (window as unknown as { __abertos: unknown[][] }).__abertos);
  expect(abertos[0]?.[0]).toBe("https://www.instagram.com/fabionunes_14/");
  await page.screenshot({ path: `${CAPTURAS}/T-W24-redes-desktop.png`, fullPage: true });
});

test("redes: tooltip da dispersão fica inteiro dentro da janela, inclusive no ponto da borda", async ({ page }) => {
  await page.goto("/#/redes?uf=SE");
  const pontos = page.locator(".grafico-redes-dispersao circle.marca");
  await expect(pontos).toHaveCount(10);
  const vp = page.viewportSize() ?? { width: 1280, height: 720 };
  for (const id of ["7", "8", "1"]) {
    const ponto = page.locator(`.grafico-redes-dispersao circle.marca[data-id="${id}"]`);
    await ponto.scrollIntoViewIfNeeded();
    await ponto.hover();
    const balao = page.locator(".tooltip-flutuante:not([hidden])");
    await expect(balao).toContainText("Seguidores");
    await expect(balao).toContainText("esperado");
    const caixa = await balao.boundingBox();
    expect(caixa).not.toBeNull();
    expect(caixa?.x).toBeGreaterThanOrEqual(0);
    expect(caixa?.y).toBeGreaterThanOrEqual(0);
    expect((caixa?.x ?? 0) + (caixa?.width ?? 0)).toBeLessThanOrEqual(vp.width);
    expect((caixa?.y ?? 0) + (caixa?.height ?? 0)).toBeLessThanOrEqual(vp.height);
    await page.mouse.move(2, 2);
  }
});

test("redes: ranking compacto (10 por lista) e busca acha quem está fora dele", async ({ page }) => {
  await page.goto("/#/redes?uf=SE");
  const ranking = page.locator(".ranking-Seguidores");
  await expect(ranking.locator("rect.marca")).toHaveCount(10);
  await expect(page.locator(".rankings-redes svg.grafico")).toHaveCount(3);
  await page.getByLabel("Escolher candidato em foco").fill("hugo");
  await page.getByRole("button", { name: /Hugo Alves/ }).click();
  await expect(page.locator(".foco-cartao")).toContainText("Hugo Alves");
  await expect(page.locator(".grafico-redes-ritmo rect.marca[data-serie=candidato]").first()).toBeVisible();
});

test("redes: série com 1 ponto mostra o número e a nota; com 2 pontos, a linha", async ({ page }) => {
  await page.goto("/#/redes?uf=SE");
  await expect(page.locator(".serie-numero")).toContainText("52.000 seguidores");
  await expect(page.locator(".serie-seguidores")).toContainText("A série cresce a cada dia.");
  await expect(page.locator(".serie-seguidores svg")).toHaveCount(0);

  await page.unroute("**/api/**");
  await simularApi(page, { "/api/redes/serie": { status: 200, corpo: SERIE_2 } });
  await page.goto("/#/redes?uf=SE&x=1");
  await page.reload();
  await expect(page.locator(".grafico-redes-serie path.linha-serie")).toBeVisible();
  await expect(page.locator(".serie-resumo")).toContainText("+340 seguidores (+0,65 %) em 1 dia");
  await expect(page.locator(".grafico-redes-serie circle.marca")).toHaveCount(2);
});

test("redes: perfil indisponível aparece como indisponível, com link do TSE, nunca como zero", async ({ page }) => {
  await page.goto("/#/redes?uf=SE");
  await page.getByLabel("Escolher candidato em foco").fill("kesia");
  await page.getByRole("button", { name: /perfil indisponível/ }).click();
  const cartao = page.locator(".foco-cartao");
  await expect(cartao).toContainText("Perfil indisponível");
  await expect(cartao).not.toContainText(/\b0 seguidores/);
  await expect(cartao.getByRole("link", { name: "Página no TSE" })).toHaveAttribute("href", /divulgacandcontas/);
  await expect(page.locator(".serie-seguidores")).toContainText("Sem série");
  await page.screenshot({ path: `${CAPTURAS}/T-W24-redes-indisponivel.png`, fullPage: false });
});

test("redes: no celular tudo empilha, sem rolagem horizontal", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#/redes?uf=SE");
  await expect(page.locator(".grafico-redes-dispersao circle.marca")).toHaveCount(10);
  const larg = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, vis: window.innerWidth }));
  expect(larg.doc).toBeLessThanOrEqual(larg.vis);
  await page.screenshot({ path: `${CAPTURAS}/T-W24-redes-mobile.png`, fullPage: true });
});
