// Autoridades que atribuyen, confirman o investigan incidentes, escritas para que se entiendan
// sin saber su idioma: el nombre traducido y, en las instituciones, el original entre
// paréntesis («el Gobierno federal alemán (Bundesregierung)»). Las claves son los nombres tal
// como los guarda la base. Una autoridad que no está en la tabla llega traducida en los datos
// publicados (`autoridades`, exportacion/citas.py), que se apuntan al validarlos; si aún no hay
// traducción, se escribe «una autoridad»: nunca un nombre en otro idioma (tests/fichas.test.tsx).

import tabla from "../../../configuracion/autoridades.json" with { type: "json" };
import type { Idioma } from "../sitio.ts";

interface Autoridad {
  es: string;
  en: string;
  /** Una institución: lleva su nombre original entre paréntesis. */
  original?: boolean;
}

// La tabla, revisada a mano, está en configuracion/autoridades.json (la usan también los avisos).
export const AUTORIDADES: Readonly<Record<string, Autoridad>> = tabla.autoridades;

const SIN_NOMBRE = { es: "una autoridad", en: "an authority" } as const;

/** Las autoridades traducidas que traen los datos publicados (nombre en forma compuesta). */
const TRADUCIDAS = new Map<string, { es: string; en: string }>();

/** Apunta las autoridades traducidas de un incidente, un ataque o un impacto (datos/validar.ts). */
export function anadirAutoridades(traducidas: Readonly<Record<string, { es: string; en: string }>>): void {
  for (const [nombre, traduccion] of Object.entries(traducidas)) {
    if (traduccion.es.trim() !== "" && traduccion.en.trim() !== "") TRADUCIDAS.set(nombre.normalize("NFC"), traduccion);
  }
}

/** Si la autoridad se sabe escribir en el idioma de la web (está en la tabla o llegó traducida). */
export function autoridadConocida(original: string): boolean {
  const nombre = original.normalize("NFC");
  return AUTORIDADES[nombre] !== undefined || TRADUCIDAS.has(nombre);
}

/**
 * La autoridad escrita en el idioma de la web: «el Gobierno federal alemán (Bundesregierung)».
 * Primero la tabla, revisada a mano; después la traducción que traen los datos; si no hay
 * ninguna, «una autoridad»: nunca un nombre en otro idioma ni en otro alfabeto.
 */
export function autoridadEscrita(original: string, idioma: Idioma): string {
  // Las fuentes escriben a veces las tildes como signo aparte: se compara en forma compuesta.
  const nombre = original.normalize("NFC");
  const conocida = AUTORIDADES[nombre];
  if (conocida !== undefined) {
    return conocida.original === true ? `${conocida[idioma]} (${original})` : conocida[idioma];
  }
  return TRADUCIDAS.get(nombre)?.[idioma] ?? SIN_NOMBRE[idioma];
}

const DECLARACION = /^(.+) \(declaración oficial citada en (.+)\)$/;

/**
 * El nombre de una fuente para la ficha. Una declaración oficial citada por un medio («X
 * (declaración oficial citada en medio)», como la guarda la base) se escribe en el idioma de la
 * web con la autoridad traducida; las demás, tal cual.
 */
export function medioEscrito(
  medio: string,
  idioma: Idioma,
  declaracion: (autoridad: string, medio: string) => string,
): string {
  const partes = DECLARACION.exec(medio);
  if (partes === null) {
    // Una fuente oficial sin medio (el Gobierno, la policía, el tráfico medido, un canal
    // oficial): su nombre traducido, en mayúscula como nombre de la fuente. Un medio con dominio
    // (un periódico) sale tal cual.
    if (!autoridadConocida(medio) && medio.includes(".")) return medio;
    const escrita = autoridadEscrita(medio, idioma);
    return escrita.charAt(0).toUpperCase() + escrita.slice(1);
  }
  const [, autoridad = "", fuente = ""] = partes;
  return declaracion(autoridadEscrita(autoridad, idioma), fuente);
}

/**
 * La fuente dentro de una frase («según el Ministerio de Defensa de Rumanía», «según news.az»):
 * como medioEscrito, pero sin la mayúscula del nombre de la fuente.
 */
export function medioEnFrase(
  medio: string,
  idioma: Idioma,
  declaracion: (autoridad: string, medio: string) => string,
): string {
  const escrito = medioEscrito(medio, idioma, declaracion);
  return escrito === medio ? medio : escrito.charAt(0).toLowerCase() + escrito.slice(1);
}
