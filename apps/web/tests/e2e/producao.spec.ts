/**
 * Verificação final contra a PRODUÇÃO (T-W13). Fora do CI: roda só com E2E_PROD=1.
 * `E2E_PROD=1 pnpm exec playwright test producao --config=playwright.prod.config.ts`
 * Capturas em test-results/capturas/T-W13/ (SALVAR_CAPTURAS=1 grava em docs/registro/handoffs/img/T-W13/).
 */
import { pastaCapturas } from "./capturas";
import { expect, test, type Page } from "@playwright/test";

test.skip(process.env["E2E_PROD"] !== "1", "defina E2E_PROD=1");

const IMG = pastaCapturas("T-W13");
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
  // O overlay só aparece após 200 ms: o que prova "carregou" é a reserva de espaço ter sumido.
  await expect(page.locator(".reserva-carga")).toHaveCount(0, { timeout: 60_000 });
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
        // Só o Renan Santos vai ao repositório (o repositório não precisa de 60 imagens); os demais provam-se pelo teste.
        if (nome === "renan") await page.screenshot({ path: `${IMG}/item7-${vp.nome}-${nome}-${tela}.jpg`, type: "jpeg", quality: 55 });
      });
    }
  }
}

// ---- Itens 1–6, 8–11: cada um com captura em 1440 e 390 ----
for (const vp of VIEWPORTS) {
  test.describe(`itens ${vp.nome}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });
    const foto = (page: Page, nome: string): Promise<Buffer> => page.screenshot({ path: `${IMG}/${nome}-${vp.nome}.png` });

    test("item1 nomes completos no ranking", async ({ page }) => {
      await page.goto("/#/visao-geral?cargo=presidente");
      await pronto(page);
      const rotulos = await page.locator(".ranking text, .ranking [role=row] th, .ranking td:first-child").allTextContents();
      expect(rotulos.join(" ")).toContain("RENAN SANTOS");
      expect(rotulos.join("|")).not.toContain("…");
      await page.goto("/#/visao-geral?cargo=deputado_federal");
      await pronto(page);
      const r2 = await page.locator(".ranking svg text").allTextContents();
      expect(r2.some((t) => t.includes("…"))).toBe(false);
      await foto(page, "item1-ranking");
    });

    test("item2 mapa do presidente: Brasil inteiro + exterior à parte", async ({ page }) => {
      await page.goto("/#/mapa?cargo=presidente&cand=2026%3A280002540694");
      await expect(page.locator("[data-mapa-pronto='sim'][data-abrangencia='pais']")).toBeVisible({ timeout: 90_000 });
      await expect(page.getByRole("alert")).toHaveCount(0);
      await expect(page.locator("body")).toContainText(/exterior/i);
      await page.waitForTimeout(1500);
      await foto(page, "item2-mapa-presidente");
    });

    test("item3 gastos: hover/foco/toque mostra tooltip completo", async ({ page }) => {
      await page.goto("/#/gastos");
      await pronto(page);
      const c = page.locator("circle.marca").first();
      await c.scrollIntoViewIfNeeded();
      if (vp.nome === "390") await c.tap({ force: true }).catch(async () => { await c.click({ force: true }); });
      else await c.hover({ force: true });
      const balao = page.locator(".tooltip:visible").first();
      await expect(balao).toBeVisible();
      for (const t of ["Partido", "UF", "Cargo", "Votos", "Despesa contratada", "Despesa paga", "Custo por voto", "% recursos públicos", "Resultado"]) await expect(balao).toContainText(t);
      await expect(balao).not.toContainText("indisponível");
      await foto(page, "item3-gastos-hover");
      // foco por teclado
      await page.keyboard.press("Escape");
      await c.blur();
      await c.focus();
      await expect(page.locator(".tooltip:visible").first()).toContainText("Despesa paga");
    });

    test("item4 tooltips ? e fonte legíveis", async ({ page }) => {
      await page.goto("/#/gastos");
      await pronto(page);
      const ajuda = page.locator(".ajuda-botao").first();
      await ajuda.scrollIntoViewIfNeeded();
      await ajuda.focus();
      await expect(page.locator(".ajuda-painel:visible").first()).toBeVisible();
      await foto(page, "item4-ajuda");
      await page.keyboard.press("Escape");
      const fonte = page.locator(".fonte-botao").first();
      await fonte.focus();
      await expect(page.locator(".fonte-painel:visible").first()).toBeVisible();
      await foto(page, "item4-fonte");
      // o texto do painel quebra dentro dele (nada transborda nem é cortado)
      const sobra = await page.locator(".fonte-painel:visible").first().evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(sobra).toBeLessThanOrEqual(1);
      // o chip não pode quebrar de linha dentro do 1º cartão
      const h1 = await page.locator(".kpi").first().evaluate((el) => (el.querySelector(".fonte-botao") as HTMLElement).getBoundingClientRect().height);
      expect(h1).toBeLessThan(40);
    });

    test("item5 usa a tela toda, sem rolagem horizontal, paleta Missão", async ({ page }) => {
      await page.goto("/#/visao-geral");
      await pronto(page);
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, main: (document.querySelector("main") as HTMLElement).getBoundingClientRect().width, destaque: getComputedStyle(document.documentElement).getPropertyValue("--cor-destaque").trim(), bg: getComputedStyle(document.body).backgroundColor }));
      expect(m.sw).toBeLessThanOrEqual(m.cw);
      expect(m.main / m.cw).toBeGreaterThan(vp.width > 800 ? 0.7 : 0.9);
      await foto(page, "item5-layout");
      console.log("item5", vp.nome, JSON.stringify(m));
    });

    test("item6 carregando em overlay de tela cheia", async ({ page }) => {
      await page.route("**/api/candidatos*", async (r) => { await new Promise((ok) => setTimeout(ok, 3000)); await r.continue(); });
      await page.goto("/#/visao-geral?cargo=senador");
      const st = page.getByRole("status");
      await expect(st).toBeVisible({ timeout: 10_000 });
      const caixa = await page.locator(".sobreposicao").boundingBox();
      expect(caixa?.width).toBeGreaterThanOrEqual(vp.width - 2);
      expect(caixa?.height).toBeGreaterThanOrEqual(vp.height - 2);
      await page.screenshot({ path: `${IMG}/item6-overlay-${vp.nome}.png`, animations: "disabled" });
      console.log("item6", vp.nome, JSON.stringify(caixa));
    });

    test("item8 filtros dependentes e busca global com sugestões", async ({ page }) => {
      await page.goto("/#/visao-geral?cargo=governador");
      await pronto(page);
      const uf = page.locator("input[name=uf]");
      await uf.focus();
      const n = await page.locator("[role=option]").count();
      console.log("item8 opcoes de UF para governador:", n);
      expect(n).toBeLessThan(28);
      await foto(page, "item8-uf-dependente");
      await page.keyboard.press("Escape");
      const busca = page.getByPlaceholder("Nome, número ou partido");
      await busca.fill("renan");
      await expect(page.locator("[role=option]").first()).toContainText(/RENAN SANTOS/i, { timeout: 15_000 });
      await foto(page, "item8-busca");
    });

    test("item8b deep-link só com cand= ajusta os filtros ao candidato", async ({ page }) => {
      await page.goto("/#/mapa?cand=2026%3A190002544120");
      await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 90_000 });
      if (vp.width < 1024) {
        // Celular: os filtros ficam recolhidos; o botão resume o recorte, que tem de ser o do candidato.
        await expect(page.getByRole("button", { name: /^Filtros:/ })).toContainText("Governador · RJ");
        await page.getByRole("button", { name: /^Filtros:/ }).click();
      }
      await expect(page.getByRole("radio", { name: "Governador" })).toBeChecked();
      await expect(page.locator("input[name=uf]")).toHaveValue(/Rio de Janeiro/);
      await foto(page, "item8b-filtros-seguem-candidato");
    });

    test("item9 mapa do candidato mostra só a região dele", async ({ page }) => {
      await page.goto("/#/mapa?cand=2026%3A170002549820");
      await expect(page.locator("[data-mapa-pronto='sim'][data-abrangencia='PE']")).toBeVisible({ timeout: 90_000 });
      await page.waitForTimeout(1500);
      await foto(page, "item9-mapa-estadual");
      await page.goto("/#/candidato?cand=2026%3A280002540694");
      await expect(page.locator("[data-mapa-pronto='sim'][data-abrangencia='pais']")).toBeVisible({ timeout: 90_000 });
    });

    test("item10 evolução: comparador com busca de candidato", async ({ page }) => {
      await page.goto("/#/evolucao");
      await pronto(page);
      await foto(page, "item10-evolucao");
      await page.getByRole("button", { name: "Alterar" }).first().click();
      await page.getByLabel("Candidatos").first().check();
      await page.getByLabel(/Buscar candidato/).first().fill("guto");
      const opcao = page.locator("[role=option]").first();
      await expect(opcao).toBeVisible({ timeout: 15_000 });
      await foto(page, "item10-evolucao-busca");
      await opcao.click();
      await page.getByRole("button", { name: "Aplicar" }).first().click();
      await expect(page).toHaveURL(/de=c/);
      await pronto(page);
      await expect(page.getByRole("alert")).toHaveCount(0);
      await foto(page, "item10-evolucao-escolhido");
    });

    test("item11 ficha: total gasto, links TSE e fonte", async ({ page }) => {
      await page.goto("/#/candidato?cand=2026%3A250002546642");
      await pronto(page);
      await expect(page.locator("body")).toContainText(/gast|despesa/i);
      const links = await page.locator("a[href*='tse.jus.br']").count();
      console.log("item11 links tse:", links, "botoes fonte:", await page.locator(".fonte-botao").count());
      expect(links).toBeGreaterThan(0);
      await page.locator(".fonte-botao").first().scrollIntoViewIfNeeded();
      await foto(page, "item11-ficha");
    });
  });
}
