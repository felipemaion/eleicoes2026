import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { simularApi } from "./api";

const lerJson = (nome: string): Record<string, unknown> => JSON.parse(readFileSync(new URL(`../fixtures/api/${nome}.json`, import.meta.url), "utf-8")) as Record<string, unknown>;

/** Candidato falso com a abrangência do cargo: presidente = país; os demais = UF. */
async function comCandidato(page: Page, sq: string, nome: string, cargo: string, uf: string): Promise<void> {
  const ficha = lerJson("ficha") as { candidato: Record<string, unknown> };
  const pais = cargo === "PRESIDENTE";
  ficha.candidato = { ...ficha.candidato, sq_candidato: Number(sq), nm_urna: nome, cargo, sg_uf: pais ? "BR" : uf, abrangencia: pais ? { tipo: "pais", uf: null } : { tipo: "uf", uf } };
  const mapa = { ...lerJson("mapa"), votos_fora_do_mapa: pais ? 8580 : 0 };
  await page.route(`**/api/candidatos/2026/${sq}`, (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify(ficha) }));
  await page.route("**/api/mapa?**", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify(mapa) }));
}

test.beforeEach(async ({ page }) => { await simularApi(page); });

test("busca: '/' foca, sugestão traz contexto e destaque, Enter abre a ficha", async ({ page }) => {
  await page.goto("/#/visao-geral");
  await page.keyboard.press("/");
  const busca = page.getByRole("combobox", { name: "Buscar candidato" });
  await expect(busca).toBeFocused();
  await busca.fill("candid");
  const opcao = page.getByRole("listbox", { name: "Candidaturas encontradas" }).getByRole("option").first();
  await expect(opcao).toContainText("2026 · Deputado federal · SE · MISSÃO (14) · 12.345 votos");
  await expect(opcao.locator("mark")).toHaveText(/candid/i);
  await expect(busca).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#\/candidato\?uf=SE&cand=2026%3A1/);
  await expect(page.getByRole("heading", { level: 2, name: "Ana Souza" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("busca: Shift+Enter fixa o candidato no mapa, que mostra só a UF dele", async ({ page }) => {
  await page.goto("/#/visao-geral");
  const busca = page.getByRole("combobox", { name: "Buscar candidato" });
  await busca.fill("candid");
  await expect(page.getByRole("listbox", { name: "Candidaturas encontradas" }).getByRole("option")).toHaveCount(1);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Shift+Enter");
  await expect(page).toHaveURL(/#\/mapa\?uf=SE&cand=2026%3A1/);
  await expect(page.locator(".mapa-foco")).toContainText("Mostrando só onde disputou: Sergipe");
  await expect(page.locator("[data-mapa-pronto='sim'][data-abrangencia='SE']")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Ver o grupo todo" }).click();
  await expect(page).not.toHaveURL(/cand=/);
});

test("busca sem resultado e com API fora do ar têm mensagem própria", async ({ page }) => {
  await page.route("**/api/busca?**", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify({ total: 0, limite: 8, itens: [], dt_geracao: "2026-10-07" }) }));
  await page.goto("/");
  const busca = page.getByRole("combobox", { name: "Buscar candidato" });
  await busca.fill("zzzz");
  await expect(page.locator(".busca-estado")).toContainText("Nenhum candidato encontrado");
  await page.unroute("**/api/busca?**");
  await page.route("**/api/busca?**", (r) => r.fulfill({ status: 500, body: "{}" }));
  await busca.fill("yyyy");
  await expect(page.locator(".busca-estado")).toContainText("Busca indisponível");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("filtros: chips de ano/cargo, UF com busca, grupo com descrição, contagem e limpar", async ({ page }) => {
  await page.goto("/#/visao-geral");
  const filtros = page.getByRole("form", { name: "Filtros" });
  await expect(filtros.locator(".filtros-contagem")).toContainText(/candidatura/);
  await filtros.getByText("2022", { exact: true }).click();
  await filtros.getByText("Senador", { exact: true }).click();
  await expect(page).toHaveURL(/cargo=senador/);
  await expect(page).toHaveURL(/ano=2022/);
  await filtros.getByLabel("Estado (UF)").fill("serg");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/uf=SE/);
  await filtros.getByLabel("Grupo comparado").selectOption("mbl_2022");
  await expect(filtros.locator(".filtro-grupo-desc")).toContainText("MBL");
  await filtros.getByRole("button", { name: "Limpar filtros" }).click();
  await expect(page).toHaveURL(/#\/visao-geral$/);
  await expect(filtros.getByRole("button", { name: "Limpar filtros" })).toBeHidden();
});

test("filtros: presidente leva a Brasil, trava a UF e nunca soma cargos", async ({ page }) => {
  await page.goto("/#/mapa?uf=SP");
  const filtros = page.getByRole("form", { name: "Filtros" });
  await filtros.getByText("Presidente", { exact: true }).click();
  await expect(page).toHaveURL(/cargo=presidente/);
  await expect(page).not.toHaveURL(/uf=/);
  await expect(filtros.getByLabel("Estado (UF)")).toBeDisabled();
  await expect(filtros).toContainText("eleição nacional");
});

test("avisos compactos: essencial à vista, o resto recolhido e os KPIs sobem", async ({ page }) => {
  await page.goto("/#/mapa?uf=SE");
  const resto = page.locator("details.avisos-resto");
  await expect(resto.locator("summary")).toContainText(/Notas sobre os dados \(\d+\)/);
  await expect(resto).not.toHaveAttribute("open", "");
});

const CASOS: [string, string, string, string, string][] = [
  ["Renan Santos (presidente)", "280002540694", "RENAN SANTOS", "PRESIDENTE", "BR"],
  ["Kim Kataguiri (deputado federal)", "250002546642", "KIM KATAGUIRI", "DEPUTADO FEDERAL", "SP"],
  ["senador", "120002535769", "CAPITÃO CONTAR", "SENADOR", "MS"],
  ["deputado estadual", "170002549820", "DEPUTADA ESTADUAL", "DEPUTADO ESTADUAL", "PE"],
];
for (const [rotulo, sq, nome, cargo, uf] of CASOS) {
  test(`ficha e mapa sem erro genérico: ${rotulo}`, async ({ page }) => {
    await comCandidato(page, sq, nome, cargo, uf);
    await page.goto(`/#/candidato?cand=2026%3A${sq}`);
    await expect(page.getByRole("heading", { level: 2, name: nome })).toBeVisible();
    const esperado = cargo === "PRESIDENTE" ? "pais" : uf;
    await expect(page.locator(`[data-mapa-pronto='sim'][data-abrangencia='${esperado}']`)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText("Não foi possível carregar os dados agora")).toHaveCount(0);
    if (cargo === "PRESIDENTE") await expect(page.getByText("Votos no exterior: 8.580 (fora do mapa).")).toBeVisible();
    await page.goto(`/#/mapa?cand=2026%3A${sq}`);
    await expect(page.locator(".mapa-foco")).toContainText(nome);
    await expect(page.locator(`[data-mapa-pronto='sim'][data-abrangencia='${esperado}']`)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("grupos: o seletor lista todos os grupos da API e trocar de grupo recarrega KPIs e mapa", async ({ page }) => {
  const urls = await simularApi(page);
  await page.goto("/#/visao-geral");
  const filtros = page.getByRole("form", { name: "Filtros" });
  const seletor = filtros.getByLabel("Grupo comparado");
  await expect(seletor.locator("option")).toHaveText(["Partido Missão 2026", "MBL 2026 (Missão + aliados em outros partidos)", "MBL 2022", "MBL 2022 — indicados"]);
  await seletor.selectOption("mbl_2026");
  await expect(page).toHaveURL(/grupo=mbl_2026/);
  await expect(filtros.locator(".filtro-grupo-desc")).toContainText("aliados");
  await expect.poll(() => urls.some((u) => u.startsWith("/api/candidatos?") && u.includes("grupo=mbl_2026"))).toBe(true);
  await page.goto("/#/mapa?grupo=mbl_2026");
  await expect.poll(() => urls.some((u) => u.startsWith("/api/mapa?") && u.includes("grupo=mbl_2026"))).toBe(true);
});

test("grupos: a Evolução abre em MBL 2022 → MBL 2026 quando o grupo é mbl_2026, e os grupos viram opções dos cartões", async ({ page }) => {
  const urls = await simularApi(page);
  await page.goto("/#/evolucao?grupo=mbl_2026");
  await expect(page.locator(".frase-resumo")).toContainText("MBL 2026");
  await page.getByRole("button", { name: "Alterar" }).nth(1).click();
  await expect(page.locator(".cartao-lado").nth(1).locator("select[name=grupo] option")).toContainText(["Partido Missão 2026", "MBL 2026 (Missão + aliados em outros partidos)"]);
  await expect.poll(() => urls.some((u) => u.startsWith("/api/comparativo?") && u.includes("comparacao=mbl2022_mbl2026"))).toBe(true);
});
