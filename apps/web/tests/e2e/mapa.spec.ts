import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("mapa carrega a fixture, troca indicador sem recarregar geometria e mostra tooltip", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE");
  const area = page.locator("[data-mapa-pronto='sim']");
  await expect(area).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-quadro canvas")).toBeVisible();

  // legenda com unidade e denominador
  const legenda = page.locator(".mapa-legenda svg");
  await expect(legenda).toContainText("Denominador");
  await expect(legenda).toContainText("eleitores aptos");
  await expect(legenda).toContainText("Penetração");

  const antes = await area.evaluate((e) => ({ f: e.getAttribute("data-fontes"), a: e.getAttribute("data-atualizacoes") }));
  expect(antes.f).toBe("1");

  await page.getByLabel("Indicador").selectOption("pct_validos");
  await expect(area).toHaveAttribute("data-atualizacoes", String(Number(antes.a) + 1));
  await expect(area).toHaveAttribute("data-fontes", "1"); // geometria não recarregou
  await expect(legenda).toContainText("votos válidos");

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
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await page.getByText("Tabela de valores").click();
  await expect(page.locator(".mapa-tabela tbody tr, .mapa-tabela tr")).toHaveCount(75); // cabeçalho + 74 municípios com dado (1 sem denominador fica fora)
});

test("sair da tela do mapa libera o WebGL (sem canvas órfão)", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("navigation", { name: "Telas" }).getByRole("link", { name: "Gastos" }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
});

test("criar e destruir o mapa 20× não esgota contextos WebGL", async ({ page }) => {
  const avisos: string[] = [];
  page.on("console", (m) => { if (m.text().includes("Too many active WebGL contexts")) avisos.push(m.text()); });
  await page.goto("/#/mapa?uf=SE");
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
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-quadro canvas")).toHaveAttribute("tabindex", "-1");
  await page.keyboard.press("Tab");
  await page.locator(".mapa-quadro").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.locator("body").click({ position: { x: 1, y: 1 } });
  await expect(page.getByRole("tooltip")).toBeHidden();
});

test("teclado: Enter no município destacado abre o painel lateral com o foco no título", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await page.locator(".mapa-quadro").focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  const painel = page.locator(".painel-municipio");
  await expect(painel.locator("h2")).toBeFocused();
  await expect(painel).toContainText("Missão 2026");
  await expect(painel.locator("table").first()).toBeVisible();
});

test("clique no município abre o painel lateral", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  // O "Carregando…" some depois do mapa pronto e desloca o layout: espera antes de medir.
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.locator(".mapa-quadro").scrollIntoViewIfNeeded();
  const caixa = await page.locator(".mapa-quadro canvas").boundingBox();
  if (!caixa) throw new Error("canvas sem caixa");
  const x = caixa.x + caixa.width / 2;
  const y = caixa.y + caixa.height / 2;
  // O WebGL pode demorar a desenhar os polígonos após "pronto": repete o hover até haver feição sob o cursor.
  await expect(async () => {
    await page.mouse.move(x - 3, y - 3);
    await page.mouse.move(x, y, { steps: 4 });
    await expect(page.getByRole("tooltip")).toBeVisible({ timeout: 500 });
  }).toPass({ timeout: 10_000 });
  await page.mouse.down();
  await page.mouse.up();
  await expect(page.locator(".painel-municipio h2")).toBeVisible();
});

test("pontos 503: o coroplético renderiza, a densidade fica desligada e o aviso é discreto", async ({ page }) => {
  await simularApi(page, { "/api/mapa/pontos": { status: 503 } });
  const erros: string[] = [];
  page.on("pageerror", (e) => { erros.push(e.message); });
  await page.goto("/#/mapa?uf=SE");
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".mapa-quadro canvas")).toBeVisible();
  // Densidade nasce desligada: o mapa nem pede os pontos até o usuário ligar.
  await expect(page.getByLabel(/Densidade de votos/)).not.toBeChecked();
  await expect(page.locator(".estado.erro")).toHaveCount(0);
  // Ligar a densidade com a API fora do ar: aviso amigável (sem URL crua) e checkbox desabilitado.
  // click(), não check(): o app desmarca o checkbox sozinho ao receber o 503, e check() reprova
  // se essa reversão chegar antes da conferência de estado (corrida). O resultado é esperado abaixo.
  await page.getByLabel(/Densidade de votos/).click();
  const aviso = page.locator(".aviso-pontos");
  await expect(aviso).toContainText("indisponível");
  await expect(aviso).not.toContainText("/api/");
  await expect(page.getByLabel(/Densidade de votos/)).toBeDisabled();
  await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible();
  expect(erros).toEqual([]);
});

test("erro de API não mostra a URL crua nem estoura a largura", async ({ page }) => {
  await simularApi(page, { "/api/mapa": { status: 503 } });
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/#/mapa?uf=SE");
  const caixa = page.locator(".estado.erro").first();
  await expect(caixa).toBeVisible();
  await expect(caixa).not.toContainText("/api/");
  const estoura = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(estoura).toBe(false);
});

test.describe("divisória mapa × painel", () => {
  test.use({ viewport: { width: 1400, height: 900 } });
  const larguras = (page: import("@playwright/test").Page) => page.evaluate(() => ({
    canvas: document.querySelector<HTMLCanvasElement>(".mapa-quadro canvas")?.clientWidth ?? 0,
    painel: document.querySelector<HTMLElement>(".painel-municipio")?.getBoundingClientRect().width ?? 0,
  }));

  test("arrastar muda as larguras, o canvas acompanha e setas/Home/dblclick/persistência funcionam", async ({ page }) => {
    await page.goto("/#/mapa?uf=SE");
    await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
    const sep = page.getByRole("separator");
    await expect(sep).toHaveAttribute("aria-orientation", "vertical");
    const antes = await larguras(page);
    const c = await sep.boundingBox();
    if (!c) throw new Error("divisória sem caixa");
    await page.mouse.move(c.x + c.width / 2, c.y + c.height / 2);
    await page.mouse.down();
    await page.mouse.move(c.x - 120, c.y + c.height / 2, { steps: 5 });
    await page.mouse.up();
    await expect(async () => {
      const depois = await larguras(page);
      expect(depois.painel).toBeGreaterThan(antes.painel + 80);
      expect(depois.canvas).toBeLessThan(antes.canvas - 80);
    }).toPass({ timeout: 5_000 });

    const agora = Number(await sep.getAttribute("aria-valuenow"));
    await sep.focus();
    await page.keyboard.press("ArrowRight");
    expect(Number(await sep.getAttribute("aria-valuenow"))).toBeLessThan(agora);
    await page.keyboard.press("Home");
    expect(Number(await sep.getAttribute("aria-valuenow"))).toBe(Number(await sep.getAttribute("aria-valuemin")));

    await page.keyboard.press("End");
    const guardada = await sep.getAttribute("aria-valuenow");
    await page.reload();
    await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("separator")).toHaveAttribute("aria-valuenow", guardada ?? "");

    await page.getByRole("separator").dblclick();
    expect(Number(await page.getByRole("separator").getAttribute("aria-valuenow"))).toBeLessThan(Number(guardada));
  });

  test("tela estreita: sem divisória", async ({ page }) => {
    await page.setViewportSize({ width: 800, height: 900 });
    await page.goto("/#/mapa?uf=SE");
    await expect(page.getByRole("separator")).toBeHidden();
  });

  test("tabela do painel: nenhuma célula quebra linha", async ({ page }) => {
    await page.goto("/#/mapa?uf=SE");
    await expect(page.locator("[data-mapa-pronto='sim']")).toBeVisible({ timeout: 15_000 });
    await page.locator(".mapa-quadro").focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Enter");
    await expect(page.locator(".painel-municipio table").first()).toBeVisible();
    const quebras = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".tabela-painel th, .tabela-painel td")]
      .filter((c) => c.getBoundingClientRect().height > parseFloat(getComputedStyle(c).lineHeight) + 12).length);
    expect(quebras).toBe(0);
  });
});
