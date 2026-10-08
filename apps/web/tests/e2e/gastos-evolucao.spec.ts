import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { simularApi } from "./api";
import { pastaCapturas } from "./capturas";

const CAPTURAS = pastaCapturas();

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("gastos: hover e foco no círculo mostram o tooltip com os dados do candidato", async ({ page }) => {
  await page.goto("/#/gastos");
  const ponto = page.locator('.grafico-despesa circle.marca[data-id="1"]');
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
  const ana = page.locator('.grafico-despesa circle.marca[data-id="1"]');
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
  const sem = page.locator('.grafico-despesa circle.marca[data-id="3"]');
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

/** Resposta de antes do deploy que trouxe foto e link: o ETag da API não muda com o código, então o navegador a reaproveita. */
const semFotoNemLink = (corpo: string): string => {
  const g = JSON.parse(corpo) as { por_candidato: Record<string, unknown>[] };
  return JSON.stringify({ ...g, por_candidato: g.por_candidato.map((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== "foto_url" && k !== "link_tse_candidato"))) });
};

test("gastos (T-W21): resposta antiga em cache não esconde foto e link — a API é chamada com a versão do build", async ({ page }) => {
  await page.route("**/fotos/**", (r) => r.fulfill({ contentType: "image/png", body: PIXEL }));
  const completo = readFileSync(new URL("../fixtures/api/gastos.json", import.meta.url), "utf-8");
  // Registrada depois de `simularApi` (beforeEach), portanto tem prioridade.
  await page.route("**/api/gastos?**", (r) => {
    const sujeitoAoCacheAntigo = !new URL(r.request().url()).searchParams.has("v");
    return r.fulfill({ contentType: "application/json", body: sujeitoAoCacheAntigo ? semFotoNemLink(completo) : completo });
  });
  for (const alvo of ["/#/gastos?uf=SE", "/#/gastos?uf=SE&grupo=mbl_2026"]) {
    await page.goto(alvo);
    const pontos = page.locator("circle.marca");
    await expect(pontos.first()).toBeVisible();
    await expect(page.locator("svg.grafico > title")).toHaveCount(0);
    await expect(page.locator("circle.marca title")).toHaveCount(0);
    const balao = page.locator(".tooltip-flutuante:not([hidden])");
    for (let i = 0; i < await pontos.count(); i++) {
      await page.mouse.move(2, 2);
      await pontos.nth(i).hover();
      await expect(balao.locator(".foto-candidato")).toBeVisible();
      await expect(balao).toContainText("Clique para abrir no TSE");
    }
  }
});

test("gastos: a busca realça o candidato e a linha tracejada mostra a mediana", async ({ page }) => {
  await page.goto("/#/gastos");
  await expect(page.locator("line.referencia")).toHaveCount(2);
  await page.getByLabel("Realçar candidato nos gráficos").fill("bruno");
  await expect(page.locator('.grafico-despesa circle.marca[data-id="2"]')).toHaveClass(/destaque/);
  await expect(page.locator('.grafico-despesa circle.marca[data-id="1"]')).toHaveClass(/atenuado/);
  await expect(page.locator(".busca-gastos-estado")).toContainText("1 candidato");
  await page.screenshot({ path: `${CAPTURAS}/T-W12-gastos-busca.png` });
  await page.locator("rect.marca").first().hover();
  await expect(page.locator(".tooltip-flutuante:not([hidden])")).toContainText("R$");
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

test("financiamento (T-W16): receita × votos com hover, saldo, clique no TSE e comparação 2022→2026 corrigida", async ({ page }) => {
  await page.route("**/fotos/**", (r) => r.fulfill({ contentType: "image/png", body: PIXEL }));
  await page.addInitScript(() => {
    (window as unknown as { __abertos: unknown[][] }).__abertos = [];
    window.open = ((...a: unknown[]) => { (window as unknown as { __abertos: unknown[][] }).__abertos.push(a); return null; });
  });
  await page.goto("/#/gastos");
  await expect(page.getByRole("heading", { level: 1, name: "Financiamento" })).toBeVisible();
  const kpis = page.locator("dl.kpis").first();
  for (const t of ["Receita total do grupo", "Receita por voto", "% recursos públicos", "% autofinanciamento", "% pessoas físicas", "Saldo da campanha"]) await expect(kpis).toContainText(t);
  const ana = page.locator('.grafico-receita circle.marca[data-id="1"]');
  await ana.hover();
  const balao = page.locator(".tooltip-flutuante:not([hidden])");
  for (const t of ["Receita total", "Receita por voto", "Saldo (receita − despesa contratada)", "% pessoas físicas"]) await expect(balao).toContainText(t);
  await expect(balao.locator("img")).toHaveAttribute("alt", "Foto de Ana Souza");
  await ana.click();
  const abertos = await page.evaluate(() => (window as unknown as { __abertos: unknown[][] }).__abertos);
  expect(abertos[0]?.[0]).toBe("https://divulgacandcontas.tse.jus.br/divulga/#/candidato/BR/SE/2026/1");
  const tabela = page.locator("table.tabela-comparativo-receitas");
  await expect(tabela).toContainText("set/2026");
  await expect(tabela).toContainText("+11,5%");
  await page.screenshot({ path: `${CAPTURAS}/T-W16-financiamento.png`, fullPage: true });
});
