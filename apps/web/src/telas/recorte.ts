/** Liga as telas de candidato ao store sem acoplá-las a ele: o recorte dos filtros segue o candidato aberto. */
import { filtrosDoCandidato } from "../dados/adaptadores";
import type { Filtros } from "../store";

type Ajustador = (f: Partial<Filtros>) => void;
let ajustador: Ajustador | null = null;

/** Registrada por `main.ts`; sem ela (testes de tela) o recorte simplesmente não é ajustado. */
export function definirAjustadorDeRecorte(a: Ajustador | null): void { ajustador = a; }

/** Chamada quando a ficha chega: cargo/UF/ano/grupo dos filtros passam a refletir quem está na tela. */
export function seguirCandidato(c: { ano: number; cargo: string; sg_uf: string }): void { ajustador?.(filtrosDoCandidato(c)); }
