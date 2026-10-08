import { defineConfig } from "@playwright/test";

/** Config da verificação em produção (T-W13): sem servidor local. */
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  workers: 3,
  use: { baseURL: process.env["E2E_BASE"] ?? "https://eleicoes2026.maionesys.com" },
});
