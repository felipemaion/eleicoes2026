/**
 * Serve `data/processed/tiles` em `/tiles/` no `vite dev` e `vite preview`, com suporte a Range
 * (PMTiles lê o arquivo por faixas de bytes). Só desenvolvimento: em produção é o Caddy.
 */
import { createReadStream, statSync } from "node:fs";
import { resolve, sep } from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

const PREFIXO = "/tiles/";

/** Caminho do arquivo pedido dentro de `raiz`, ou `null` se fora de /tiles/ ou com travessia. */
export function caminhoSeguro(raiz: string, urlPath: string): string | null {
  if (!urlPath.startsWith(PREFIXO)) return null;
  let relativo: string;
  try { relativo = decodeURIComponent(urlPath.slice(PREFIXO.length)); } catch { return null; }
  const alvo = resolve(raiz, relativo);
  return alvo === raiz || alvo.startsWith(raiz + sep) ? alvo : null;
}

export type FaixaBytes = { inicio: number; fim: number };

/** `null` = sem Range (arquivo inteiro); `"invalido"` = 416. */
export function lerRange(cabecalho: string | undefined, tamanho: number): FaixaBytes | "invalido" | null {
  if (cabecalho === undefined) return null;
  const m = /^bytes=(\d*)-(\d*)$/.exec(cabecalho);
  if (!m || (m[1] === "" && m[2] === "")) return "invalido";
  if (m[1] === "") { const n = Number(m[2]); return n === 0 ? "invalido" : { inicio: Math.max(0, tamanho - n), fim: tamanho - 1 }; }
  const inicio = Number(m[1]);
  const fim = m[2] === "" ? tamanho - 1 : Math.min(Number(m[2]), tamanho - 1);
  return inicio >= tamanho || inicio > fim ? "invalido" : { inicio, fim };
}

function atender(raiz: string, req: IncomingMessage, res: ServerResponse, seguinte: () => void): void {
  const url = new URL(req.url ?? "/", "http://localhost");
  const alvo = caminhoSeguro(raiz, url.pathname);
  if (alvo === null || (req.method !== "GET" && req.method !== "HEAD")) { seguinte(); return; }
  let tamanho: number;
  try {
    const st = statSync(alvo);
    if (!st.isFile()) { seguinte(); return; }
    tamanho = st.size;
  } catch {
    // Sem arquivo = tiles ainda não gerados: 404 de verdade (o front cai na geometria de demonstração).
    res.statusCode = 404;
    res.end();
    return;
  }
  const tipo = alvo.endsWith(".json") ? "application/json" : "application/octet-stream";
  const faixa = lerRange(req.headers.range, tamanho);
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("Content-Type", tipo);
  // Arquivos têm hash no nome; o manifesto não, e precisa revalidar.
  res.setHeader("Cache-Control", alvo.endsWith("manifesto.json") ? "no-cache" : "public, max-age=31536000, immutable");
  if (faixa === "invalido") { res.statusCode = 416; res.setHeader("Content-Range", `bytes */${String(tamanho)}`); res.end(); return; }
  if (faixa === null) { res.setHeader("Content-Length", String(tamanho)); }
  else {
    res.statusCode = 206;
    res.setHeader("Content-Range", `bytes ${String(faixa.inicio)}-${String(faixa.fim)}/${String(tamanho)}`);
    res.setHeader("Content-Length", String(faixa.fim - faixa.inicio + 1));
  }
  if (req.method === "HEAD") { res.end(); return; }
  createReadStream(alvo, faixa === null ? undefined : { start: faixa.inicio, end: faixa.fim }).pipe(res);
}

export function servirTiles(pasta: string): Plugin {
  const raiz = resolve(pasta);
  const usar = (s: { middlewares: { use: (f: (req: IncomingMessage, res: ServerResponse, next: () => void) => void) => void } }): void => {
    s.middlewares.use((req, res, next) => { atender(raiz, req, res, next); });
  };
  return { name: "servir-tiles", configureServer: usar, configurePreviewServer: usar };
}
