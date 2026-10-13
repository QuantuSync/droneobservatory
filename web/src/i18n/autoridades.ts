// Autoridades que atribuyen, confirman o investigan incidentes, escritas para que se entiendan
// sin saber su idioma: el nombre traducido y, en las instituciones, el original entre
// paréntesis («el Gobierno federal alemán (Bundesregierung)»). Las claves son los nombres tal
// como los guarda la base. Una autoridad que no está aquí se escribe tal cual (la prueba de las
// fichas, tests/fichas.test.tsx, la señala).

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

const OTRA_ESCRITURA = /[^\p{Script=Latin}\p{Script=Common}\p{Script=Inherited}]/u;
const SIN_NOMBRE = { es: "una autoridad", en: "an authority" } as const;

/**
 * La autoridad escrita en el idioma de la web: «el Gobierno federal alemán (Bundesregierung)».
 * Una que no está en la tabla sale tal cual si va en alfabeto latino (su nombre propio); en otra
 * escritura, «una autoridad»: nunca otro alfabeto en la página.
 */
export function autoridadEscrita(original: string, idioma: Idioma): string {
  // Las fuentes escriben a veces las tildes como signo aparte: se compara en forma compuesta.
  const conocida = AUTORIDADES[original.normalize("NFC")];
  if (conocida === undefined) return OTRA_ESCRITURA.test(original) ? SIN_NOMBRE[idioma] : original;
  return conocida.original === true ? `${conocida[idioma]} (${original})` : conocida[idioma];
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
    // Una fuente oficial sin medio (el Gobierno, la policía, el tráfico medido): su nombre
    // traducido, en mayúscula como nombre de la fuente.
    if (AUTORIDADES[medio.normalize("NFC")] === undefined) return medio;
    const escrita = autoridadEscrita(medio, idioma);
    return escrita.charAt(0).toUpperCase() + escrita.slice(1);
  }
  const [, autoridad = "", fuente = ""] = partes;
  return declaracion(autoridadEscrita(autoridad, idioma), fuente);
}
