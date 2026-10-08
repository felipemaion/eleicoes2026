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

// Candidatos reais de cada abrangência: presidente (país), deputado federal, senador e deputado estadual.
const REAIS: [string, string, string][] = [
  ["Renan Santos (presidente)", "280002540694", "pais"],
  ["Kim Kataguiri", "250002546642", "SP"],
  ["senador (Capitão Contar)", "120002535769", "MS"],
  ["deputado estadual", "170002549820", "PE"],
];
for (const [rotulo, sq, abrangencia] of REAIS) {
  test(`API real: ficha e mapa focado carregam sem erro — ${rotulo}`, async ({ page }) => {
    await page.goto(`/#/candidato?cand=2026%3A${sq}`);
    await expect(page.locator(".ficha h2")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator(`[data-mapa-pronto='sim'][data-abrangencia='${abrangencia}']`)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
    await page.goto(`/#/mapa?cand=2026%3A${sq}`);
    await expect(page.locator(`[data-mapa-pronto='sim'][data-abrangencia='${abrangencia}']`)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("API real: a busca acha 'renan santos' e abre a ficha", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("/");
  await page.getByRole("combobox", { name: "Buscar candidato" }).fill("renan santos");
  await expect(page.getByRole("listbox", { name: "Candidaturas encontradas" }).getByRole("option").first()).toContainText("Presidente");
  await page.keyboard.press("Enter");
  await expect(page.locator(".ficha h2")).toContainText("RENAN SANTOS", { timeout: 30_000 });
  await expect(page.getByRole("alert")).toHaveCount(0);
});
