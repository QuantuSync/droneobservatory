// Nombres de lugar que dan las fuentes, escritos para quien lee cada versión de la web.
//
// El extractor guarda el lugar como lo escribe la fuente: un nombre propio (que se deja tal cual:
// «Portul Constanța», «Brussels Airport»), pero a veces una descripción genérica en otra lengua
// («exclusive economic zone», «gare de triage de Mulhouse», «eastern Latvia»), un nombre en otra
// escritura («София», «Αιγαίο») o el nombre inglés de una ciudad que en español tiene el suyo
// («Warsaw»). Estos se escriben aquí en los dos idiomas. Lo que no está en la tabla:
// - en cirílico o en griego, se pasa al alfabeto latino;
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

const CIRILICO: Readonly<Record<string, string>> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ж: "zh", з: "z", и: "i", й: "y", к: "k", л: "l",
  м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "ts", ч: "ch",
  ш: "sh", щ: "sht", ъ: "a", ь: "", ю: "yu", я: "ya", є: "ye", і: "i", ї: "yi", ґ: "g", ы: "y", э: "e", ё: "yo",
};
const GRIEGO: Readonly<Record<string, string>> = {
  α: "a", ά: "a", β: "v", γ: "g", δ: "d", ε: "e", έ: "e", ζ: "z", η: "i", ή: "i", θ: "th", ι: "i",
  ί: "i", ϊ: "i", κ: "k", λ: "l", μ: "m", ν: "n", ξ: "x", ο: "o", ό: "o", π: "p", ρ: "r", σ: "s",
  ς: "s", τ: "t", υ: "y", ύ: "y", φ: "f", χ: "ch", ψ: "ps", ω: "o", ώ: "o",
};
const OTRA_ESCRITURA = /[Ͱ-Ͽἀ-῿Ѐ-ӿ]/;

/** Pasa al alfabeto latino un nombre en cirílico o en griego, conservando las mayúsculas. */
export function latino(nombre: string): string {
  return [...nombre]
    .map((letra) => {
      const minuscula = letra.toLowerCase();
      const cambio = CIRILICO[minuscula] ?? GRIEGO[minuscula];
      if (cambio === undefined) return letra;
      return letra === minuscula ? cambio : cambio.charAt(0).toUpperCase() + cambio.slice(1);
    })
    .join("");
}

/** El nombre de un lugar para la página en `idioma`; null si no se debe enseñar. */
export function nombreDeLugar(nombre: string, idioma: Idioma): string | null {
  const escrito = NOMBRES_LUGAR[nombre];
  if (escrito !== undefined) return escrito[idioma];
  if (OTRA_ESCRITURA.test(nombre)) return latino(nombre);
  const primera = nombre.charAt(0);
  if (primera !== primera.toUpperCase()) return null;
  return nombre;
}
