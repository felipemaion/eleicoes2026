import { expect, test, type Page } from "@playwright/test";
import { simularApi } from "./api";

test.beforeEach(async ({ page }) => { await simularApi(page); });

const TELAS = ["Visão geral", "Mapa", "Financiamento", "Evolução 2022×2026", "Candidato", "Redes sociais", "Como ler"];

const semRolagemHorizontal = async (page: Page): Promise<number> =>
  await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

for (const vp of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
  test.describe(`cabeçalho compacto ${String(vp.width)}×${String(vp.height)}`, () => {
    test.use({ viewport: vp });

    test("barra única de até 64 px, fixa ao rolar, sem rolagem horizontal", async ({ page }) => {
      await page.goto("/#/visao-geral");
      const topo = page.locator("header.topo");
      expect((await topo.boundingBox())?.height ?? 999).toBeLessThanOrEqual(64);
      await expect(page.getByRole("navigation", { name: "Telas" })).toBeHidden();
      await page.evaluate(() => { window.scrollTo(0, 600); });
      expect((await topo.boundingBox())?.y).toBe(0);
      expect(await semRolagemHorizontal(page)).toBeLessThanOrEqual(0);
    });

    test("menu ☰: abre, navega, fecha com Esc, ao tocar fora e prende o foco", async ({ page }) => {
      await page.goto("/#/visao-geral");
      const botao = page.getByRole("button", { name: "Menu" });
      const nav = page.getByRole("navigation", { name: "Telas" });
      await expect(botao).toHaveAttribute("aria-expanded", "false");
      await botao.click();
      await expect(botao).toHaveAttribute("aria-expanded", "true");
      for (const nome of TELAS) await expect(nav.getByRole("link", { name: nome })).toBeVisible();
      await expect(page.getByRole("button", { name: "Tema claro" })).toBeVisible();

      // Foco preso: Tab repetido nunca sai do cabeçalho.
      for (let i = 0; i < 12; i++) {
        await page.keyboard.press("Tab");
        expect(await page.evaluate(() => !!document.activeElement?.closest("header.topo"))).toBe(true);
      }
      await page.keyboard.press("Escape");
      await expect(botao).toHaveAttribute("aria-expanded", "false");
      await expect(botao).toBeFocused();

      await botao.click();
      await page.mouse.click(vp.width / 2, vp.height - 20);
      await expect(botao).toHaveAttribute("aria-expanded", "false");

      await botao.click();
      await nav.getByRole("link", { name: "Mapa" }).click();
      await expect(page).toHaveURL(/#\/mapa/);
      await expect(botao).toHaveAttribute("aria-expanded", "false");
      await expect(page.getByRole("heading", { level: 1, name: "Mapa" })).toBeVisible();
    });

    test("tema claro fica dentro do menu", async ({ page }) => {
      await page.goto("/#/visao-geral");
      await expect(page.getByRole("button", { name: "Tema claro" })).toBeHidden();
      await page.getByRole("button", { name: "Menu" }).click();
      await page.getByRole("button", { name: "Tema claro" }).click();
      await expect(page.locator("html")).toHaveAttribute("data-tema", "claro");
    });

    test("busca: ícone abre o campo por cima da barra, funciona e fecha com Esc", async ({ page }) => {
      await page.goto("/#/visao-geral");
      const abrir = page.getByRole("button", { name: "Buscar" });
      await expect(page.getByLabel("Buscar candidato")).toBeHidden();
      await abrir.click();
      await expect(abrir).toHaveAttribute("aria-expanded", "true");
      const campo = page.getByLabel("Buscar candidato");
      await expect(campo).toBeFocused();
      expect((await page.locator("header.topo").boundingBox())?.height ?? 999).toBeLessThanOrEqual(64);
      await campo.fill("kim");
      await expect(page.getByRole("option").first()).toBeVisible();
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
      await expect(campo).toBeHidden();
      await expect(abrir).toBeFocused();
    });

    test("filtros: botão com resumo abre painel sobre o conteúdo e aplica", async ({ page }) => {
      await page.goto("/#/mapa");
      const botao = page.locator(".lateral-alternar");
      await expect(botao).toContainText("Filtros");
      const main = page.locator("main");
      const antes = (await main.boundingBox())?.y ?? 0;
      await botao.click();
      await expect(botao).toHaveAttribute("aria-expanded", "true");
      expect((await main.boundingBox())?.y).toBe(antes); // painel flutua: não empurra o conteúdo
      await page.getByLabel("Estado (UF)").fill("são pau");
      await page.getByRole("option", { name: "São Paulo (SP)" }).click();
      await expect(page).toHaveURL(/uf=SP/);
      await expect(botao).toContainText("SP");
      await page.keyboard.press("Escape");
      await expect(botao).toHaveAttribute("aria-expanded", "false");
    });
  });
}

test("desktop (1280): navegação e tema continuam na barra, sem botões móveis", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/#/visao-geral");
  await expect(page.getByRole("navigation", { name: "Telas" }).getByRole("link", { name: "Como ler" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tema claro" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Menu" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Buscar", exact: true })).toBeHidden();
});
