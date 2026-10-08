// Gera public/og.png uma única vez (rode: node scripts-dev/gerar-og.mjs). O PNG é versionado.
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
await p.goto(new URL("./og.html", import.meta.url).href);
await p.screenshot({ path: fileURLToPath(new URL("../public/og.png", import.meta.url)) });
await b.close();
