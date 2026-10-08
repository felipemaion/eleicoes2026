import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { simularApi } from "./api";

const CAPTURAS = "../../docs/registro/handoffs/img";
// O tipo é só para quem chama (JSON.parse devolve any).
// eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
const fixture = <T>(nome: string): T => JSON.parse(readFileSync(new URL(`../fixtures/api/${nome}.json`, import.meta.url), "utf-8")) as T;

type Cand = Record<string, unknown> & { sq_candidato: number; ano: number; nm_urna: string };
const base = fixture<{ itens: Cand[] }>("busca").itens[0] as Cand;
const CANDIDATURAS: Cand[] = [
  { ...base, ano: 2022, sq_candidato: 111, nm_urna: "GUTO ZACARIAS", uf: "SP", cargo: "DEPUTADO ESTADUAL", indicado: true },
  { ...base, ano: 2026, sq_candidato: 222, nm_urna: "RAFA MINATO", uf: "SP", cargo: "DEPUTADO ESTADUAL", indicado: false },
  { ...base, ano: 2022, sq_candidato: 301, nm_urna: "KIM KATAGUIRI", uf: "SP", cargo: "DEPUTADO FEDERAL", indicado: true },
  { ...base, ano: 2022, sq_candidato: 302, nm_urna: "CRISTIANO BERALDO", uf: "SP", cargo: "DEPUTADO FEDERAL", indicado: true },
];

/** `/busca` e as fichas respondem por ano/nome; o `/comparativo` ecoa a contagem pedida e guarda as URLs. */
async function simular(page: Page, contagem: { nDe: number; nPara: number }): Promise<string[]> {
  const urls = await simularApi(page);
  const comparativo = fixture<Record<string, unknown>>("comparativo");
  const ficha = fixture<{ candidato: Cand }>("ficha");
  await page.route("**/api/busca?**", (r) => {
    const q = new URL(r.request().url()).searchParams;
    const termo = (q.get("q") ?? "").toLowerCase();
    const itens = CANDIDATURAS.filter((c) => String(c.ano) === q.get("ano") && c.cargo === q.get("cargo") && c.nm_urna.toLowerCase().includes(termo));
    return r.fulfill({ contentType: "application/json", body: JSON.stringify({ total: itens.length, limite: 40, itens, dt_geracao: "2026-10-07" }) });
  });
  await page.route(/\/api\/candidatos\/(2022|2026)\/\d+$/, (r) => {
    const [, ano, sq] = /candidatos\/(\d+)\/(\d+)/.exec(r.request().url()) ?? [];
    const c = CANDIDATURAS.find((x) => String(x.ano) === ano && String(x.sq_candidato) === sq);
    return r.fulfill({ contentType: "application/json", body: JSON.stringify({ ...ficha, candidato: { ...ficha.candidato, ...c, sg_uf: "SP" } }) });
  });
  await page.route("**/api/comparativo?**", (r) => {
    const u = new URL(r.request().url());
    urls.push(u.pathname + u.search);
    return r.fulfill({ contentType: "application/json", body: JSON.stringify({ ...comparativo, n_de: contagem.nDe, n_para: contagem.nPara, uf: "SP" }) });
  });
  return urls;
}

async function escolherCandidato(page: Page, cartao: number, busca: string, nome: string): Promise<void> {
  const c = page.locator(".cartao-lado").nth(cartao);
  await c.getByRole("button", { name: "Alterar" }).click();
  await c.getByLabel("Candidatos").check();
  await c.getByLabel(/Buscar candidato/).fill(busca);
  await c.getByRole("option", { name: new RegExp(nome) }).click();
}

test("comparador: Guto Zacarias 2022 × Rafa Minato 2026 (dep. estadual SP) em poucos cliques; a URL reproduz o estado", async ({ page }) => {
  const urls = await simular(page, { nDe: 1, nPara: 1 });
  await page.goto("/#/evolucao?uf=SP&cargo=deputado_estadual");
  await escolherCandidato(page, 0, "guto", "GUTO ZACARIAS");
  await expect(page.locator(".chip-candidato")).toContainText("GUTO ZACARIAS");
  await expect(page.locator(".chip-candidato .selo")).toHaveText("indicado MBL");
  await page.locator(".cartao-lado").first().getByRole("button", { name: "Aplicar" }).click();
  await expect(page).toHaveURL(/de=c(:|%3A)111/);
  await escolherCandidato(page, 1, "rafa", "RAFA MINATO");
  await page.locator(".cartao-lado").nth(1).getByRole("button", { name: "Aplicar" }).click();
  await expect(page).toHaveURL(/para=c(:|%3A)222/);

  const frase = page.locator(".frase-resumo");
  await expect(frase).toContainText("Comparando GUTO ZACARIAS (2022) com RAFA MINATO (2026)");
  await expect(frase).toContainText("Deputado estadual · São Paulo");
  await expect(frase).toContainText("1 candidatura → 1 candidatura");
  await expect(page.locator("dl.kpis")).toContainText("Penetração em 2022");
  await expect(page.locator("dl.kpis")).toContainText("6,1 ‰");
  expect(urls.some((u) => u.startsWith("/api/comparativo?") && u.includes("sq_2022=111") && u.includes("sq_2026=222"))).toBe(true);
  await expect(page.locator("table.tabela-pessoas tbody tr")).toHaveCount(2);

  // Nenhuma lista longa: nada com mais de 8 itens visíveis.
  const maior = await page.evaluate(() => Math.max(0, ...[...document.querySelectorAll("ul,ol")].filter((l) => (l as HTMLElement).offsetParent !== null && !l.closest("nav")).map((l) => l.children.length)));
  expect(maior).toBeLessThanOrEqual(8);
  await page.screenshot({ path: `${CAPTURAS}/T-W20-guto-rafa-desktop.png`, fullPage: true });

  await page.reload();
  await expect(frase).toContainText("Comparando GUTO ZACARIAS (2022) com RAFA MINATO (2026)");
  await expect(page).toHaveURL(/de=c(:|%3A)111/);
});

test("comparador: Kim + Beraldo 2022 × Partido Missão 2026 inteiro (dep. federal SP) — 'ver quanto expandimos'", async ({ page }) => {
  const urls = await simular(page, { nDe: 2, nPara: 49 });
  await page.goto("/#/evolucao?uf=SP");
  await escolherCandidato(page, 0, "kim", "KIM KATAGUIRI");
  await page.locator(".cartao-lado").first().getByLabel(/Buscar candidato/).fill("beraldo");
  await page.getByRole("option", { name: /CRISTIANO BERALDO/ }).click();
  await expect(page.locator(".chip-candidato")).toHaveCount(2);
  await page.locator(".cartao-lado").first().getByRole("button", { name: "Aplicar" }).click();

  const frase = page.locator(".frase-resumo");
  await expect(frase).toContainText("Comparando KIM KATAGUIRI + CRISTIANO BERALDO (2022) com Partido Missão 2026 (2026)");
  await expect(frase).toContainText("2 candidaturas → 49 candidaturas");
  expect(urls.some((u) => u.startsWith("/api/comparativo?") && u.includes("sq_2022=301") && u.includes("sq_2022=302") && u.includes("grupo_2026=missao_2026") && !u.includes("mesmos_candidatos"))).toBe(true);
  await page.screenshot({ path: `${CAPTURAS}/T-W20-kim-beraldo-missao-desktop.png`, fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".cartoes-lados")).toBeVisible();
  const semRolagem = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const largos = await page.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).slice(0, 6).map((e) => `${e.tagName}.${e.className}`));
  expect(semRolagem, `estouram a largura: ${largos.join(", ")}`).toBe(true);
  await page.screenshot({ path: `${CAPTURAS}/T-W20-kim-beraldo-missao-mobile.png`, fullPage: true });

  await page.reload();
  await expect(frase).toContainText("KIM KATAGUIRI + CRISTIANO BERALDO");
  await page.getByRole("button", { name: /Limpar/ }).click();
  await expect(page).not.toHaveURL(/de=/);
  await expect(frase).toContainText("MBL 2022");
});

test("comparador: 422 sq_fora_do_recorte aparece como mensagem no cartão do lado, sem quebrar a tela", async ({ page }) => {
  await simular(page, { nDe: 1, nPara: 1 });
  await page.route("**/api/comparativo?**", (r) => r.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: { codigo: "sq_fora_do_recorte" } }) }));
  await page.goto("/#/evolucao?uf=SP&de=c:301");
  await expect(page.locator(".cartao-erro-api")).toContainText("não concorreu a este cargo nesta UF");
  await expect(page.locator(".cartao-lado")).toHaveCount(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
});
