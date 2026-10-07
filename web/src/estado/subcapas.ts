// Subcapas de la capa de guerra en la dirección: «Corredores», «Rutas» y «Con satélite» (y el
// filtro de la lista de «Con satélite»). Así un enlace compartido las abre como estaban. Las
// subcapas no se encienden solas: sin nada en la dirección, apagadas.

import { TIPOS_SATELITE } from "../datos/guerraSatelite.ts";
import type { TipoSatelite } from "../datos/guerraSatelite.ts";

export const PARAMETRO_GUERRA = "guerra";
export const PARAMETRO_SATELITE = "satelite";

export interface Subcapas {
  corredores: boolean;
  satelite: boolean;
  rutas: boolean;
  /** Tipos a los que se limita la lista de «Con satélite»; vacío, todos. */
  filtro: TipoSatelite[];
}

export const SIN_SUBCAPAS: Subcapas = { corredores: false, satelite: false, rutas: false, filtro: [] };

/** Nombres que se aceptan en `satelite=` para cada tipo (los de las capas retiradas incluidos:
 * «luz» y «focos» llevaban a lo que ahora es «Con satélite» con ese filtro). */
const ALIAS: Record<string, TipoSatelite[]> = {
  cortinilla: ["cortinilla"],
  imagen: ["cortinilla"],
  foco: ["foco"],
  focos: ["foco"],
  focos24h: ["foco"],
  apagon: ["apagon"],
  oscura: ["oscura"],
  luz: ["apagon", "oscura"],
  "luz-nocturna": ["apagon", "oscura"],
};

/** Las subcapas encendidas en la dirección; null si no dice nada de ellas. */
export function leerSubcapas(busqueda: string): Subcapas | null {
  const parametros = new URLSearchParams(busqueda);
  const guerra = (parametros.get(PARAMETRO_GUERRA) ?? "").split(",").filter(Boolean);
  const satelite = parametros.get(PARAMETRO_SATELITE);
  if (guerra.length === 0 && satelite === null) return null;
  const filtro = (satelite ?? "")
    .split(",")
    .flatMap((nombre) => ALIAS[nombre.trim().toLowerCase()] ?? []);
  return {
    corredores: guerra.includes("corredores"),
    satelite: guerra.includes("satelite") || satelite !== null,
    rutas: guerra.includes("rutas"),
    filtro: TIPOS_SATELITE.filter((tipo) => filtro.includes(tipo)),
  };
}

/** La búsqueda con las subcapas puestas (y sin ellas si están apagadas), sin tocar lo demás. */
export function conSubcapas(busqueda: string, subcapas: Subcapas): string {
  const parametros = new URLSearchParams(busqueda);
  parametros.delete(PARAMETRO_GUERRA);
  parametros.delete(PARAMETRO_SATELITE);
  const encendidas = [
    ...(subcapas.corredores ? ["corredores"] : []),
    ...(subcapas.satelite ? ["satelite"] : []),
    ...(subcapas.rutas ? ["rutas"] : []),
  ];
  if (encendidas.length > 0) parametros.set(PARAMETRO_GUERRA, encendidas.join(","));
  if (subcapas.satelite && subcapas.filtro.length > 0) {
    parametros.set(PARAMETRO_SATELITE, subcapas.filtro.join(","));
  }
  const texto = parametros.toString().replaceAll("%2C", ",");
  return texto.length === 0 ? "" : `?${texto}`;
}
