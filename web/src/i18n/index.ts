import type { Instante, RangoODesconocido } from "../datos/tipos.ts";
import type { Jornada } from "../datos/ucrania.ts";
import type { Idioma } from "../sitio.ts";
import { fechaDeDia } from "../tiempo/dias.ts";
import { en } from "./en.ts";
import { es } from "./es.ts";
import type { FechaEscrita, Textos } from "./tipos.ts";

const TEXTOS: Record<Idioma, Textos> = { es, en };

export function textos(idioma: Idioma): Textos {
  return TEXTOS[idioma];
}

function dosCifras(n: number): string {
  return String(n).padStart(2, "0");
}

/** Fecha UTC como dd/mm/aaaa, igual en los dos idiomas. */
export function fecha(f: Date): string {
  return `${dosCifras(f.getUTCDate())}/${dosCifras(f.getUTCMonth() + 1)}/${f.getUTCFullYear()}`;
}

export function fechaDia(dia: number): string {
  return fecha(fechaDeDia(dia));
}

/** Un día UTC por partes, para escribirlo en palabras con los textos de cada idioma. */
export function fechaEscrita(dia: number): FechaEscrita {
  const f = fechaDeDia(dia);
  return { dia: f.getUTCDate(), mes: f.getUTCMonth(), anio: f.getUTCFullYear() };
}

/**
 * Lo que cubre un parte de la guerra, escrito igual en toda la web: «noche del 3 al 4 de
 * octubre» o «día 1 de octubre». `mayuscula` para empezar una frase.
 */
export function jornadaEscrita(t: Textos, j: Jornada, mayuscula = false): string {
  const texto =
    j.tipo === "noche" ? t.tiempo.noche(fechaEscrita(j.desde), fechaEscrita(j.hasta)) : t.tiempo.dia(fechaEscrita(j.desde));
  return mayuscula ? texto.charAt(0).toUpperCase() + texto.slice(1) : texto;
}

/** Hora UTC como hh:mm. */
export function hora(f: Date): string {
  return `${dosCifras(f.getUTCHours())}:${dosCifras(f.getUTCMinutes())}`;
}

export function fechaHora(valor: string): string {
  const f = new Date(valor);
  return `${fecha(f)} · ${hora(f)} UTC`;
}

/** Un instante con la precisión que declara: sin hora cuando solo se conoce el día. */
export function instante(i: Instante): string {
  const f = new Date(i.valor);
  return i.precision === "minuto" || i.precision === "hora"
    ? `${fecha(f)} · ${hora(f)} UTC`
    : fecha(f);
}

export function numero(n: number, idioma: Idioma): string {
  return new Intl.NumberFormat(idioma, { useGrouping: "always" }).format(n);
}

/** Proporción (0–1) como porcentaje con un decimal por debajo del 10 %: «2,4 %», «17 %». */
export function porcentaje(p: number, idioma: Idioma): string {
  const valor = p * 100;
  return new Intl.NumberFormat(idioma, {
    maximumFractionDigits: valor < 10 ? 1 : 0,
    minimumFractionDigits: 0,
  }).format(valor) + " %";
}

/** «12» si el rango es exacto y «2–10» si no; null cuando ninguna fuente da la cifra. */
export function rango(r: RangoODesconocido | undefined, idioma: Idioma): string | null {
  if (r === undefined || r === "desconocido") return null;
  return r.min === r.max
    ? numero(r.min, idioma)
    : `${numero(r.min, idioma)}–${numero(r.max, idioma)}`;
}

export function esRangoAbierto(r: RangoODesconocido | undefined): boolean {
  return r !== undefined && r !== "desconocido" && r.min !== r.max;
}

/** Nombre del país a partir de su código ISO 3166-1; el propio código si no se conoce. */
export function pais(codigo: string, idioma: Idioma): string {
  try {
    return new Intl.DisplayNames(idioma, { type: "region" }).of(codigo) ?? codigo;
  } catch {
    return codigo;
  }
}

/** Nombre de una región de la capa de Ucrania; el código ISO 3166-2 si no está en la tabla. */
export function region(codigo: string, idioma: Idioma): string {
  return TEXTOS[idioma].regiones[codigo] ?? codigo;
}

export type { FechaEscrita, Textos } from "./tipos.ts";
