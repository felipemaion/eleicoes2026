import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

const TELAS = ["visao-geral", "mapa?uf=SE", "gastos", "evolucao", "candidato", "como-ler"] as const;

for (const rota of TELAS) {
  test(`axe (WCAG 2.2 AA) sem violações: #/${rota}`, async ({ page }) => {
    await simularApi(page);
    await page.goto(`/#/${rota}`);
    await expect(page.locator("main h1")).toBeVisible();
    if (rota.startsWith("mapa")) await expect(page.locator(".mapa-quadro canvas")).toBeVisible({ timeout: 15_000 });
    await page.waitForLoadState("networkidle");
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
}

test("rota de hash desconhecida mostra a 404 e volta", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/nao-existe");
  await expect(page.getByRole("heading", { name: "Página não encontrada" })).toBeFocused();
  await page.getByRole("link", { name: "Ir para a visão geral" }).click();
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText("Página não encontrada");
  await expect(page.locator(".kpi").first()).toBeVisible();
});

test("rodapé: fontes, dt_geracao, metodologia e repositório; head com OG e lang", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/visao-geral");
  const rodape = page.getByRole("contentinfo");
  await expect(rodape).toContainText("TSE");
  await expect(rodape).toContainText("2026-10-07");
  await expect(rodape.getByRole("link", { name: "Metodologia" })).toHaveAttribute("href", "#/como-ler");
  await expect(rodape.getByRole("link", { name: /GitHub/ })).toHaveAttribute("href", /github\.com\/felipemaion\/eleicoes2026/);
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  for (const sel of ['meta[property="og:image"]', 'meta[name="twitter:card"]', 'meta[name="theme-color"]', 'link[rel="icon"]']) {
    await expect(page.locator(sel)).toHaveCount(1);
  }
});

test("mapa: legenda explica a hachura de n baixo e o aviso público aparece", async ({ page }) => {
  await simularApi(page);
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator(".mapa-legenda .legenda-hachura")).toContainText("menos de 20 votos esperados");
  await page.locator("aside.avisos summary").click();
  await expect(page.locator("aside.avisos").getByText("Estimativa instável")).toBeVisible();
});

test("mapa: município com menos de 20 votos esperados vira 'instável' na tabela alternativa", async ({ page }) => {
  await simularApi(page);
  const m = JSON.parse(readFileSync(new URL("../fixtures/api/mapa.json", import.meta.url), "utf-8")) as { valores: Record<string, number>; detalhes: Record<string, unknown> };
  m.detalhes["2800209"] = { votos: 3, aptos: 300, validos: 250, taxa: 10 };
  m.valores["2800209"] = 10;
  await page.route("**/api/mapa?**", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify(m) }));
  await page.goto("/#/mapa?uf=SE");
  await page.getByText("Tabela de valores").click();
  const linhasBaixas = page.locator(".mapa-tabela tbody tr, .mapa-tabela tr").filter({ hasText: "instável (n baixo)" });
  await expect(linhasBaixas).toHaveCount(1);
});
