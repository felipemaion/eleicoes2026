/// <reference types="vitest/config" />
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { servirTiles } from "./servir-tiles";

const raizDoRepo = fileURLToPath(new URL("../..", import.meta.url));

/** Sha curto do commit (CI: GITHUB_SHA); sem git, o instante do build — sempre muda a cada build. */
function versaoDoBuild(): string {
  const ci = process.env["GITHUB_SHA"];
  if (ci) return ci.slice(0, 8);
  try { return execSync("git rev-parse --short=8 HEAD", { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return Date.now().toString(36); }
}

export default defineConfig(({ command }) => ({
  server: {
    port: 5173,
    // Os textos públicos (docs/metodologia/publico) ficam fora de apps/web e entram no build por import.
    fs: { allow: [raizDoRepo] },
    proxy: {
      // API_ALVO permite apontar o dev/preview para outra API (ex.: a de um worktree em outra porta).
      "/api": process.env["API_ALVO"] ?? "http://localhost:8000",
    },
  },
  // Produção é same-origin na raiz (Caddy): `/api`, `/tiles`, `/assets`.
  base: "/",
  // Só no build: dev e testes não mandam `v` (ver src/versao.ts).
  define: { __VERSAO_BUILD__: command === "build" ? JSON.stringify(versaoDoBuild()) : "undefined" },
  build: { target: "es2022", sourcemap: true },
  test: { environment: "jsdom", setupFiles: ["tests/unit/preparar-jsdom.ts"], include: ["tests/unit/**/*.test.ts"] },
  // Em dev o ETL grava os tiles em data/processed/tiles; em produção quem serve /tiles/ é o Caddy.
  plugins: [servirTiles(fileURLToPath(new URL("../../data/processed/tiles", import.meta.url)))],
}));
