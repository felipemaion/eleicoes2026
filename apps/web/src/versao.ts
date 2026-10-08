/**
 * Versão do bundle (sha do commit), injetada pelo Vite só no build. Vai na query de cada chamada à API:
 * o ETag da API depende só de (DT_GERACAO, URL), então sem isso o navegador seguiria reaproveitando
 * (via 304) respostas guardadas antes de um deploy que mudou o formato — foi o que escondeu a foto
 * e o link do TSE em `#/gastos?uf=SP` (T-W21). Vazio em dev e nos testes: sem parâmetro.
 */
declare const __VERSAO_BUILD__: string | undefined;

export const VERSAO_BUILD: string = typeof __VERSAO_BUILD__ === "string" ? __VERSAO_BUILD__ : "";
