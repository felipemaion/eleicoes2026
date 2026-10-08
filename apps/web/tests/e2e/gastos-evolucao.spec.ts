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
