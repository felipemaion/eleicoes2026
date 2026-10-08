import { expect, test } from "@playwright/test";
import { simularApi } from "./api";

const CAPTURAS = "../../docs/registro/handoffs/img";

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("gastos: hover e foco no círculo mostram o tooltip com os dados do candidato", async ({ page }) => {
  await page.goto("/#/gastos");
  const ponto = page.locator('circle.marca[data-id="1"]');
  await expect(ponto).toBeVisible();
  await ponto.hover();
  const balao = page.locator(".tooltip-flutuante:not([hidden])");
  await expect(balao).toContainText("Ana Souza");
  for (const t of ["MISSÃO (14)", "SE", "Despesa contratada", "Despesa paga", "Custo por voto", "Resultado"]) await expect(balao).toContainText(t);
  await page.screenshot({ path: `${CAPTURAS}/T-W12-gastos-hover.png`, fullPage: false });
  await page.mouse.move(2, 2);
  await expect(balao).toBeHidden();
  await ponto.focus();
  await expect(balao).toContainText("Ana Souza");
  await page.keyboard.press("Escape");
  await expect(balao).toBeHidden();
});

const PIXEL = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

test("gastos: hover mostra a foto (ou iniciais) e clique/Enter abrem a página do TSE em nova aba", async ({ page }) => {
  await page.route("**/fotos/**", (r) => r.fulfill({ contentType: "image/png", body: PIXEL }));
  await page.addInitScript(() => {
    (window as unknown as { __abertos: unknown[][] }).__abertos = [];
    window.open = ((...a: unknown[]) => { (window as unknown as { __abertos: unknown[][] }).__abertos.push(a); return null; });
  });
  await page.goto("/#/gastos");
  const balao = page.locator(".tooltip-flutuante:not([hidden])");
  const ana = page.locator('circle.marca[data-id="1"]');
  await ana.hover();
  await expect(balao.locator("img")).toHaveAttribute("alt", "Foto de Ana Souza");
  await expect(balao.locator("img")).toHaveAttribute("loading", "eager");
  await expect(balao).toContainText("Clique para abrir no TSE");
  await ana.click();
  await ana.focus();
  await page.keyboard.press("Enter");
  const abertos = await page.evaluate(() => (window as unknown as { __abertos: unknown[][] }).__abertos);
  expect(abertos).toHaveLength(2);
  expect(abertos[0]).toEqual(["https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/SE/2026/1", "_blank", "noopener,noreferrer"]);
  // candidatura sem foto na API (sq 3): placeholder com iniciais, mesmo tamanho
  await page.mouse.move(2, 2);
  const sem = page.locator('circle.marca[data-id="3"]');
  if (await sem.count()) {
    await sem.hover();
    await expect(balao.locator(".foto-candidato.sem-foto")).toBeVisible();
  }
});

test("gastos (T-W17): com UF a foto aparece, a tabela não quebra letra a letra e o balão cabe na viewport", async ({ page }) => {
  await page.route("**/fotos/**", (r) => r.fulfill({ contentType: "image/png", body: PIXEL }));
  await page.setViewportSize({ width: 700, height: 800 });
  await page.goto("/#/gastos?uf=SE");
  const balao = page.locator(".tooltip-flutuante:not([hidden])");
  const pontos = page.locator("circle.marca");
  await expect(pontos.first()).toBeVisible();
  // O ponto mais à direita é o que mais força o reposicionamento.
  const xs = await pontos.evaluateAll((l) => l.map((c) => c.getBoundingClientRect().right));
  await pontos.nth(xs.indexOf(Math.max(...xs))).hover();
  await expect(balao.locator("img")).toBeVisible();
  await expect(page.locator("circle.marca title")).toHaveCount(0);
  const caixa = (await balao.boundingBox()) ?? { x: -1, width: 9999 };
  expect(caixa.x).toBeGreaterThanOrEqual(0);
  expect(caixa.x + caixa.width).toBeLessThanOrEqual(700);
  const linha = balao.locator("dd").first();
  const alt = await linha.evaluate((e) => ({ h: e.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(e).lineHeight) }));
  expect(alt.h).toBeLessThanOrEqual(alt.lh * 1.2);
  expect((await linha.boundingBox())?.width ?? 0).toBeGreaterThan(40);
});

test("gastos: a busca realça o candidato e a linha tracejada mostra a mediana", async ({ page }) => {
  await page.goto("/#/gastos");
  await expect(page.locator("line.referencia")).toHaveCount(1);
  await page.getByLabel("Realçar candidato no gráfico").fill("bruno");
  await expect(page.locator('circle.marca[data-id="2"]')).toHaveClass(/destaque/);
  await expect(page.locator('circle.marca[data-id="1"]')).toHaveClass(/atenuado/);
  await expect(page.locator(".busca-gastos-estado")).toContainText("1 candidato");
  await page.screenshot({ path: `${CAPTURAS}/T-W12-gastos-busca.png` });
  await page.locator("rect.marca").first().hover();
  await expect(page.locator(".tooltip-flutuante:not([hidden])")).toContainText("R$");
});

test("evolução: escolher candidatos, comparar, ver a tabela ordenável; o hash guarda a seleção", async ({ page }) => {
  await page.goto("/#/evolucao");
  const itens = page.locator(".pessoa-item");
  await expect(itens).toHaveCount(3);
  await expect(page.locator(".pessoa-item input").nth(2)).toBeDisabled();
  await page.screenshot({ path: `${CAPTURAS}/T-W12-evolucao-selecao.png`, fullPage: true });
  await itens.nth(0).getByRole("checkbox").check();
  await itens.nth(1).getByRole("checkbox").check();
  await expect(page.locator(".selecao-contagem")).toContainText("2 selecionados");
  await page.getByRole("button", { name: "Comparar selecionados" }).click();
  await expect(page).toHaveURL(/pessoas=aaaaaaaaaaaa%2Cbbbbbbbbbbbb/);
  await expect(page.locator("table.tabela-pessoas tbody tr")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Comparando 2 candidatos" })).toBeVisible();
  await page.getByRole("button", { name: "Votos 2026" }).click();
  await expect(page.locator("table.tabela-pessoas thead th[aria-sort=descending]")).toContainText("Votos 2026");
  await expect(page.locator("table.tabela-pessoas tbody tr").first()).toContainText("ANA SOUZA");
  await page.getByRole("button", { name: "Votos 2026" }).click();
  await expect(page.locator("table.tabela-pessoas tbody tr").first()).toContainText("BRUNO LIMA");
  await page.screenshot({ path: `${CAPTURAS}/T-W12-evolucao-tabela.png`, fullPage: true });
  // Recarregar preserva a escolha (deep-link).
  await page.reload();
  await expect(page.locator("table.tabela-pessoas tbody tr")).toHaveCount(2);
  await expect(page.locator(".pessoa-item input:checked")).toHaveCount(2);
  await page.getByRole("button", { name: "Grupo inteiro" }).click();
  await expect(page).not.toHaveURL(/pessoas=/);
});

test("evolução: 'Só indicados' escolhe e aplica de uma vez", async ({ page }) => {
  await page.goto("/#/evolucao");
  await expect(page.locator(".pessoa-item")).toHaveCount(3);
  await page.getByRole("button", { name: "Só indicados" }).click();
  await expect(page).toHaveURL(/pessoas=bbbbbbbbbbbb/);
  await expect(page.locator("table.tabela-pessoas tbody tr")).toHaveCount(1);
});

test("evolução: seleção sem par comparável explica o que fazer, sem alerta técnico", async ({ page }) => {
  await page.route("**/api/comparativo?**", (r) => r.fulfill({ status: 422, contentType: "application/json", body: "{}" }));
  await page.goto("/#/evolucao?pessoas=aaaaaaaaaaaa");
  await expect(page.locator(".estado.vazio")).toContainText("Nenhum dos candidatos escolhidos");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("ficha: gastos completos, links oficiais e 'fonte' acessível por teclado", async ({ page }) => {
  await page.goto("/#/candidato?cand=2026:1");
  const gastos = page.locator(".ficha-gastos");
  await expect(gastos).toContainText("com repasses");
  await expect(gastos).toContainText("Repasses são dinheiro transferido");
  const link = page.getByRole("link", { name: /DivulgaCandContas/ });
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", /noopener/);
  await expect(page.locator(".ficha-links")).toContainText("Link não verificado");
  const fonte = gastos.getByRole("button", { name: /Fonte dos dados/ });
  await fonte.focus();
  await page.keyboard.press("Enter");
  const painel = gastos.locator(".fonte-painel");
  await expect(painel).toBeVisible();
  await expect(painel).toContainText("prestacao_contas");
  await expect(painel).toContainText("07/10/2026");
  await expect(painel.getByRole("link", { name: "Metodologia" })).toBeVisible();
  await page.screenshot({ path: `${CAPTURAS}/T-W12-ficha-fonte.png`, fullPage: true });
  await page.keyboard.press("Escape");
  await expect(painel).toBeHidden();
});

test("evolução: balão de ajuda de um KPI quebra linha e fica dentro da caixa e da tela", async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto("/#/evolucao");
  const botao = page.locator(".kpi-fim .ajuda-botao").first();
  await expect(botao).toBeVisible();
  await botao.hover();
  const balao = page.locator(".ajuda-painel:visible").first();
  await expect(balao).toBeVisible();
  const m = await balao.evaluate((e) => {
    const r = e.getBoundingClientRect();
    return { sw: e.scrollWidth, cw: e.clientWidth, esq: r.left, dir: r.right, vw: document.documentElement.clientWidth, ws: getComputedStyle(e).whiteSpace };
  });
  expect(m.ws).toBe("normal");
  expect(m.sw).toBeLessThanOrEqual(m.cw);
  expect(m.esq).toBeGreaterThanOrEqual(0);
  expect(m.dir).toBeLessThanOrEqual(m.vw);
});
