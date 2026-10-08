/// <reference types="vitest/config" />
import { defineConfig } from "vite";

export default defineConfig({
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  build: { target: "es2022", sourcemap: true },
  test: { environment: "jsdom", include: ["tests/unit/**/*.test.ts"] },
});
