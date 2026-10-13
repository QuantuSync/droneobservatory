// Nombres de lugar que dan las fuentes, escritos para quien lee cada versión de la web.
//
// El extractor guarda el lugar como lo escribe la fuente: un nombre propio (que se deja tal cual:
// «Portul Constanța», «Brussels Airport»), pero a veces una descripción genérica en otra lengua
// («exclusive economic zone», «gare de triage de Mulhouse», «eastern Latvia»), un nombre en otra
// escritura («София», «Αιγαίο») o el nombre inglés de una ciudad que en español tiene el suyo
// («Warsaw»). Estos se escriben aquí en los dos idiomas. Solo para datos publicados sin el campo
// `nombres` (antes del 13 de octubre de 2026): desde entonces escribe cada nombre la publicación
// (proceso/nombres_lugar.py, datos/nombres.ts). Lo que no está en la tabla:
// - en otra escritura, no se enseña: nunca se transcribe letra a letra («Diethnís Aeroliménas»);
// - si empieza por minúscula, es una descripción y no un nombre propio: no se enseña (la ficha
//   deja el país y el titular, que sí están en el idioma de la página).

import type { Idioma } from "../sitio.ts";

type Bilingue = { es: string; en: string };

export const NOMBRES_LUGAR: Readonly<Record<string, Bilingue>> = {
  // Descripciones genéricas en la lengua de la fuente.
  "exclusive economic zone": { es: "Zona económica exclusiva", en: "Exclusive economic zone" },
  "gare de triage de Mulhouse": { es: "Estación de clasificación de Mulhouse", en: "Mulhouse marshalling yard" },
  "Nato-kaia": { es: "Muelle de la OTAN", en: "NATO quay" },
  "southeastern Lithuania": { es: "sudeste de Lituania", en: "south-eastern Lithuania" },
  "eastern Latvia": { es: "este de Letonia", en: "eastern Latvia" },
  "northern Latvia": { es: "norte de Letonia", en: "northern Latvia" },
  southeast: { es: "sudeste", en: "south-east" },
  nord: { es: "norte", en: "north" },
  "entre Radiany y Sewerynów": { es: "entre Radiany y Sewerynów", en: "between Radiany and Sewerynów" },
  // Otra escritura.
  "Васил Левски": { es: "Aeropuerto de Sofía Vasil Levski", en: "Sofia Vasil Levski Airport" },
  София: { es: "Sofía", en: "Sofia" },
  Варна: { es: "Varna", en: "Varna" },
  Αιγαίο: { es: "Egeo", en: "Aegean" },
  "Βορειοανατολικό και Κεντρικό Αιγαίο": { es: "Egeo nororiental y central", en: "North-eastern and central Aegean" },
  // Ciudades con nombre propio en español.
  Sofia: { es: "Sofía", en: "Sofia" },
  Warsaw: { es: "Varsovia", en: "Warsaw" },
  Copenhagen: { es: "Copenhague", en: "Copenhagen" },
  Gothenburg: { es: "Gotemburgo", en: "Gothenburg" },
  Chisinau: { es: "Chisináu", en: "Chișinău" },
  Berlin: { es: "Berlín", en: "Berlin" },
  Hamburg: { es: "Hamburgo", en: "Hamburg" },
  Vilnius: { es: "Vilna", en: "Vilnius" },
  Dublin: { es: "Dublín", en: "Dublin" },
  Sevilla: { es: "Sevilla", en: "Seville" },
};

const OTRA_ESCRITURA = /[^\p{Script=Latin}\p{Script=Common}\p{Script=Inherited}]/u;

/** El nombre de un lugar para la página en `idioma`; null si no se debe enseñar. */
export function nombreDeLugar(nombre: string, idioma: Idioma): string | null {
  const escrito = NOMBRES_LUGAR[nombre.normalize("NFC")];
  if (escrito !== undefined) return escrito[idioma];
  if (OTRA_ESCRITURA.test(nombre)) return null;
  const primera = nombre.charAt(0);
  if (primera !== primera.toUpperCase()) return null;
  return nombre;
}
