import { expect, test } from "@playwright/test";

test("mapa carrega a fixture, troca indicador sem recarregar geometria e mostra tooltip", async ({ page }) => {
  await page.goto("/#/mapa");
  const area = page.locator("[data-mapa-pronto='sim']");
  await expect(area).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-quadro canvas")).toBeVisible();

  // legenda com unidade e denominador
  const legenda = page.locator(".mapa-legenda svg");
  await expect(legenda).toContainText("Denominador");
  await expect(legenda).toContainText("votos válidos");

  const antes = await area.evaluate((e) => ({ f: e.getAttribute("data-fontes"), a: e.getAttribute("data-atualizacoes") }));
  expect(antes.f).toBe("1");

  await page.getByLabel("Indicador").selectOption("swing");
  await expect(area).toHaveAttribute("data-atualizacoes", String(Number(antes.a) + 1));
  await expect(area).toHaveAttribute("data-fontes", "1"); // geometria não recarregou
  await expect(legenda).toContainText("Swing");

  // tooltip por teclado
  await page.locator(".mapa-quadro").focus();
  await page.keyboard.press("ArrowRight");
  const tip = page.getByRole("tooltip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("Eleitorado");
  await expect(tip).toContainText("Votos");
  await page.keyboard.press("Escape");
  await expect(tip).toBeHidden();

  // tooltip por mouse
  const caixa = await page.locator(".mapa-quadro canvas").boundingBox();
  if (!caixa) throw new Error("canvas sem caixa");
  await page.mouse.move(caixa.x + caixa.width / 2, caixa.y + caixa.height / 2);
  await page.mouse.move(caixa.x + caixa.width / 2 + 2, caixa.y + caixa.height / 2 + 2);
  await expect(tip).toBeVisible();
});

test("tabela alternativa lista os valores do mapa", async ({ page }) => {
  await page.goto("/#/mapa");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await page.getByText("Tabela de valores").click();
  await expect(page.locator(".mapa-tabela tbody tr, .mapa-tabela tr")).toHaveCount(76); // cabeçalho + 75 municípios
});

test("sair da tela do mapa libera o WebGL (sem canvas órfão)", async ({ page }) => {
  await page.goto("/#/mapa");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("navigation", { name: "Telas" }).getByRole("link", { name: "Gastos" }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
});

test("criar e destruir o mapa 20× não esgota contextos WebGL", async ({ page }) => {
  const avisos: string[] = [];
  page.on("console", (m) => { if (m.text().includes("Too many active WebGL contexts")) avisos.push(m.text()); });
  await page.goto("/#/mapa");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  const nav = page.getByRole("navigation", { name: "Telas" });
  for (let i = 0; i < 20; i++) {
    await nav.getByRole("link", { name: "Gastos" }).click();
    await expect(page.locator("canvas")).toHaveCount(0);
    await nav.getByRole("link", { name: "Mapa" }).click();
    await expect(page.locator(".mapa-quadro canvas")).toHaveCount(1);
  }
  expect(avisos).toEqual([]);
});

test("teclado: o canvas não é focável e as setas funcionam com o foco no quadro", async ({ page }) => {
  await page.goto("/#/mapa");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-quadro canvas")).toHaveAttribute("tabindex", "-1");
  await page.keyboard.press("Tab");
  await page.locator(".mapa-quadro").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.locator("body").click({ position: { x: 1, y: 1 } });
  await expect(page.getByRole("tooltip")).toBeHidden();
});
