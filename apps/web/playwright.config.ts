import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: "http://localhost:4173" },
  webServer: { command: "pnpm build && pnpm preview --port 4173", url: "http://localhost:4173", reuseExistingServer: true },
});
