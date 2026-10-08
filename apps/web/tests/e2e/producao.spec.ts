/**
 * Verificação final contra a PRODUÇÃO (T-W13). Fora do CI: roda só com E2E_PROD=1.
 * `E2E_PROD=1 pnpm exec playwright test producao --config=playwright.prod.config.ts`
 * Anexa capturas em docs/registro/handoffs/img/T-W13/.
 */
import { expect, test, type Page } from "@playwright/test";

test.skip(process.env["E2E_PROD"] !== "1", "defina E2E_PROD=1");

const IMG = "../../docs/registro/handoffs/img/T-W13";
const TELAS_5 = ["visao-geral", "mapa", "gastos", "evolucao", "candidato"] as const;
const CANDIDATOS: [string, string][] = [
  ["renan", "2026:280002540694"],
  ["kim", "2026:250002546642"],
  ["guto", "2026:250002546631"],
  ["senador", "2026:120002535769"],
  ["governador", "2026:190002544120"],
  ["estadual", "2026:170002549820"],
];
const VIEWPORTS = [
  { nome: "1440", width: 1440, height: 900 },
  { nome: "390", width: 390, height: 844 },
];

async function pronto(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => undefined);
  await expect(page.locator("main h1")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("status")).toHaveCount(0, { timeout: 60_000 });
}

for (const vp of VIEWPORTS) {
  for (const [nome, cand] of CANDIDATOS) {
    for (const tela of TELAS_5) {
      test(`item7 ${vp.nome} ${nome} ${tela}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(`/#/${tela}?cand=${encodeURIComponent(cand)}`);
        await pronto(page);
        await expect(page.getByRole("alert")).toHaveCount(0);
        await expect(page.locator("body")).not.toContainText("Não foi possível carregar");
        if (tela === "mapa" || tela === "candidato") await page.waitForTimeout(2500);
        await page.screenshot({ path: `${IMG}/item7-${vp.nome}-${nome}-${tela}.png` });
      });
    }
  }
}
